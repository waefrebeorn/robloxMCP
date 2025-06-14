import asyncio
import json
import uuid
import logging
from pathlib import Path
from typing import Any, Coroutine, Callable, Dict, List

# Using the same logger name as in other modules for consistency if configured globally
logger = logging.getLogger(__name__)

class MCPConnectionError(Exception):
    """Custom exception for MCP connection issues."""
    pass

class MCPClient:
    """Manages asynchronous communication with the Rust MCP server process."""
    def __init__(self, server_path: Path,
                 max_initial_start_attempts: int = 3, # Default values here
                 reconnect_attempts: int = 5):      # Can be overridden by config
        self.server_path = server_path
        self.process: asyncio.subprocess.Process | None = None
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.connection_lost = False
        self._stdout_task: asyncio.Task | None = None
        self._stderr_task: asyncio.Task | None = None
        self.max_initial_start_attempts = max_initial_start_attempts
        self.reconnect_attempts = reconnect_attempts

    async def _launch_server_process(self) -> bool:
        """Attempts to launch the MCP server subprocess and I/O readers."""
        if not self.server_path.exists():
            logger.error(f"MCP server executable not found at '{self.server_path}'. Cannot launch.")
            raise FileNotFoundError(f"MCP server executable not found at '{self.server_path}'.")

        logger.info(f"Attempting to launch MCP server: {self.server_path} --stdio")
        try:
            self.process = await asyncio.create_subprocess_exec(
                str(self.server_path), "--stdio",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            if self._stdout_task and not self._stdout_task.done(): self._stdout_task.cancel()
            if self._stderr_task and not self._stderr_task.done(): self._stderr_task.cancel()

            self._stdout_task = asyncio.create_task(self._read_stdout())
            self._stderr_task = asyncio.create_task(self._read_stderr())
            logger.info("MCP server subprocess launched.")
            await asyncio.sleep(2)

            # is_alive() checks self.connection_lost, which should be False after a fresh launch attempt
            # before this check. Explicitly reset it before _launch_server_process if needed,
            # but _launch_server_process itself sets it to False on perceived success.
            if self.process and self.process.returncode is None: # Primary check for process running
                self.connection_lost = False
                return True
            else:
                logger.warning("MCP server process terminated unexpectedly after launch or did not start.")
                await self._cleanup_process_resources()
                return False
        except Exception as e:
            logger.error(f"Failed to launch MCP server process: {e}", exc_info=True)
            await self._cleanup_process_resources()
            return False

    async def start(self) -> None:
        """Launches the MCP server process, with retries for initial start."""
        if not self.server_path.exists():
             raise FileNotFoundError(f"MCP server executable not found at '{self.server_path}'. Please build it with 'cargo build --release'.")

        for attempt in range(self.max_initial_start_attempts):
            logger.info(f"MCP server startup attempt {attempt + 1}/{self.max_initial_start_attempts}...")
            if await self._launch_server_process():
                logger.info("MCP server started successfully.")
                return
            if attempt < self.max_initial_start_attempts - 1:
                await asyncio.sleep(2 + attempt)
        logger.critical(f"Failed to start MCP server after {self.max_initial_start_attempts} attempts.")
        raise MCPConnectionError(f"Failed to start MCP server after {self.max_initial_start_attempts} attempts.")

    async def _cleanup_process_resources(self):
        """Cleans up resources associated with the server process."""
        if self.process:
            if self.process.returncode is None:
                try:
                    self.process.terminate()
                    await asyncio.wait_for(self.process.wait(), timeout=1.0)
                except asyncio.TimeoutError: self.process.kill()
                except ProcessLookupError: pass
            self.process = None

        for task in [self._stdout_task, self._stderr_task]:
            if task and not task.done():
                task.cancel()
                try: await task
                except asyncio.CancelledError: pass
        self._stdout_task, self._stderr_task = None, None

    async def stop(self) -> None:
        logger.info("Stopping MCP server process...")
        await self._cleanup_process_resources()
        self._clear_pending_requests(MCPConnectionError("MCP client stopped."))
        logger.info("MCP server process stopped and resources cleaned.")

    def _clear_pending_requests(self, error: Exception):
        for request_id, future in list(self.pending_requests.items()):
            if not future.done():
                future.set_exception(error)
            del self.pending_requests[request_id]

    async def reconnect(self) -> bool:
        logger.info("Attempting to reconnect to MCP server...")
        await self.stop()
        self.connection_lost = True # Explicitly set before trying to reconnect

        for attempt in range(self.reconnect_attempts):
            logger.info(f"Reconnect attempt {attempt + 1}/{self.reconnect_attempts}...")
            if await self._launch_server_process(): # This will set connection_lost to False on success
                logger.info("MCP server reconnected successfully.")
                return True # connection_lost is already False
            if attempt < self.reconnect_attempts - 1:
                await asyncio.sleep(3 + attempt * 2)

        logger.error(f"Failed to reconnect after {self.reconnect_attempts} attempts.")
        # self.connection_lost remains true
        return False

    def is_alive(self) -> bool:
        return self.process is not None and self.process.returncode is None and not self.connection_lost

    async def _read_stdout(self) -> None:
        while self.process and self.process.stdout:
            try:
                line_bytes = await asyncio.wait_for(self.process.stdout.readline(), timeout=5.0)
                if not line_bytes:
                    logger.warning("MCP stdout EOF. Server process likely terminated.")
                    self.connection_lost = True; break
                line = line_bytes.decode('utf-8').strip()
                if line: self._process_incoming_message(line)
            except asyncio.TimeoutError:
                if not (self.process and self.process.returncode is None):
                    logger.warning("MCP stdout readline timed out and process is no longer running.")
                    self.connection_lost = True; break
                continue
            except asyncio.CancelledError: logger.info("MCP stdout reader task cancelled."); break
            except Exception as e:
                logger.error(f"Error reading MCP stdout: {e}", exc_info=True)
                self.connection_lost = True; break
        logger.warning("MCP stdout reader task finished.")
        if not self.connection_lost and (not self.process or self.process.returncode is not None):
             self.connection_lost = True

    async def _read_stderr(self) -> None:
        while self.process and self.process.stderr:
            try:
                line_bytes = await asyncio.wait_for(self.process.stderr.readline(), timeout=5.0)
                if not line_bytes: logger.info("MCP stderr EOF."); break
                logger.warning(f"[MCP STDERR]: {line_bytes.decode('utf-8').strip()}")
            except asyncio.TimeoutError:
                if not (self.process and self.process.returncode is None):
                    logger.warning("MCP stderr readline timed out and process is no longer running."); break
                continue
            except asyncio.CancelledError: logger.info("MCP stderr reader task cancelled."); break
            except Exception as e: logger.error(f"Error reading MCP stderr: {e}", exc_info=True); break
        logger.warning("MCP stderr reader task finished.")

    def _process_incoming_message(self, json_str: str) -> None:
        try:
            msg = json.loads(json_str)
            request_id = msg.get("id")
            if request_id in self.pending_requests:
                future = self.pending_requests.pop(request_id)
                if not future.done(): future.set_result(msg)
            else: logger.info(f"Received unhandled MCP message (event?): {msg}")
        except json.JSONDecodeError: logger.warning(f"Skipping malformed JSON from MCP server: '{json_str}'")
        except Exception as e: logger.error(f"Unexpected error processing MCP message: {e} - Line: '{json_str}'", exc_info=True)

    async def send_request(self, method: str, params: dict, timeout: float = 60.0) -> dict:
        if not self.is_alive() or not self.process or not self.process.stdin:
            self.connection_lost = True
            err_msg = "MCP server process is not running or stdin is unavailable."
            logger.error(f"Attempted to send request but {err_msg.lower()}")
            self._clear_pending_requests(MCPConnectionError(f"Connection lost before sending request: {err_msg}"))
            raise MCPConnectionError(err_msg)

        request_id = str(uuid.uuid4())


        new_params = {"name": method, "arguments": params}
        request_payload = {"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": new_params}

        future = asyncio.Future()
        self.pending_requests[request_id] = future

        try:
            json_message = json.dumps(request_payload) + "\n"
            self.process.stdin.write(json_message.encode('utf-8'))
            await self.process.stdin.drain()
            logger.info(f"-> Sent MCP request (ID: {request_id}, Method: {method})")
            return await asyncio.wait_for(future, timeout=timeout)
        except BrokenPipeError as e:
            err_msg = f"Connection lost (BrokenPipeError): {e}"
            logger.error(f"BrokenPipeError communicating with MCP server for request {request_id}: {e}")
            self.connection_lost = True
            self._clear_pending_requests(MCPConnectionError(err_msg))
            raise MCPConnectionError(err_msg)
        except RuntimeError as e:
            err_msg = f"Connection lost (RuntimeError): {e}"
            logger.error(f"RuntimeError communicating with MCP server for request {request_id}: {e}")
            self.connection_lost = True
            self._clear_pending_requests(MCPConnectionError(err_msg))
            raise MCPConnectionError(err_msg)
        except asyncio.TimeoutError:
            logger.error(f"Request {request_id} timed out after {timeout}s.")
            if request_id in self.pending_requests: del self.pending_requests[request_id]
            raise
        except Exception as e:
            err_msg = f"Unexpected error sending request: {e}"
            logger.error(f"Unexpected error sending request {request_id}: {e}", exc_info=True)
            self.connection_lost = True
            self._clear_pending_requests(MCPConnectionError(err_msg))
            raise MCPConnectionError(err_msg)
