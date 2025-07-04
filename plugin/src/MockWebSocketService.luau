-- MockWebSocketService.luau (Corrected Singleton Version)

local HttpService = game:GetService("HttpService")

local MockWebSocketClient = {}
MockWebSocketClient.__index = MockWebSocketClient

local EnumWebSocketState = {
	Connecting = "Connecting",
	Open = "Open",
	Closing = "Closing",
	Closed = "Closed",
}

local CloseableStates = {
	[EnumWebSocketState.Connecting] = true,
	[EnumWebSocketState.Open] = true,
}

local POLL_WAIT_TIME = 1

export type MockWebSocketClient = {
	Send: (self: MockWebSocketClient, data: any) -> (),
	Close: (self: MockWebSocketClient) -> (),
	SetReceiveEndpoint: (self: MockWebSocketClient, endpoint: string) -> (),
	SetSendEndpoint: (self: MockWebSocketClient, endpoint: string) -> (),
	Opened: RBXScriptSignal,
	Closed: RBXScriptSignal,
	MessageReceived: RBXScriptSignal,
	ConnectionState: typeof(EnumWebSocketState.Connecting),
}

type MockWebSocketClientPrivate = MockWebSocketClient & {
	new: (uri: string) -> MockWebSocketClient,
	_OpenImpl: (self: MockWebSocketClient) -> (),
	_uri: string,
	_receiveEndpoint: string,
	_sendEndpoint: string,
	_pollTask: thread?,
	_OpenedEvent: BindableEvent,
	_ClosedEvent: BindableEvent,
	_MessageReceivedEvent: BindableEvent,
}

function MockWebSocketClient.new(uri: string): MockWebSocketClient
	local self: MockWebSocketClientPrivate = setmetatable({}, MockWebSocketClient) :: any

	self._uri = uri
	self._receiveEndpoint = ""
	self._sendEndpoint = ""
	self._pollTask = nil :: thread?

	self._OpenedEvent = Instance.new("BindableEvent")
	self.Opened = self._OpenedEvent.Event

	self._ClosedEvent = Instance.new("BindableEvent")
	self.Closed = self._ClosedEvent.Event

	self._MessageReceivedEvent = Instance.new("BindableEvent")
	self.MessageReceived = self._MessageReceivedEvent.Event

	self.ConnectionState = EnumWebSocketState.Connecting

	task.defer(self._OpenImpl, self)

	return self
end

local function doRequest(url: string, method: "GET" | "POST", body: any)
	local requestBody: string?
	local contentType = "application/json" -- Default to JSON

	if method == "POST" then
		if type(body) == "table" then
			local ok, encoded = pcall(HttpService.JSONEncode, HttpService, body)
			if ok then
				requestBody = encoded
			else
				warn("MockWebSocketService: Failed to JSON-encode POST body table:", tostring(encoded))
				return nil
			end
		elseif type(body) == "string" then
			requestBody = body
		else
			warn("MockWebSocketService: Unsupported POST body type:", typeof(body))
			return nil
		end
	end

	local ok, response = pcall(function()
		return HttpService:RequestAsync({
			Url = url,
			Method = method,
			Headers = {
				["Content-Type"] = contentType,
			},
			Body = requestBody,
			Compress = Enum.HttpCompression.None,
		})
	end)

	return if ok and response.Success then response else nil
end

function MockWebSocketClient._OpenImpl(self: MockWebSocketClientPrivate)
	assert(self.ConnectionState == EnumWebSocketState.Connecting, "WebSocket is not in the Connecting state")

	self.ConnectionState = EnumWebSocketState.Open
	self._OpenedEvent:Fire()

	self._pollTask = task.spawn(function()
		while self.ConnectionState == EnumWebSocketState.Open do
			-- Check connection state again before making the request
			if self.ConnectionState ~= EnumWebSocketState.Open then break end

			local response = doRequest(self._uri .. self._receiveEndpoint, "GET")

			-- And check again after the request returns
			if self.ConnectionState ~= EnumWebSocketState.Open then break end

			if response and response.Body then
				self._MessageReceivedEvent:Fire(response.Body)
			end

			task.wait(POLL_WAIT_TIME)
		end
	end)
end

function MockWebSocketClient.Send(self: MockWebSocketClientPrivate, data: any)
	doRequest(self._uri .. self._sendEndpoint, "POST", data)
end

function MockWebSocketClient.Close(self: MockWebSocketClientPrivate)
	if CloseableStates[self.ConnectionState] then
		self.ConnectionState = EnumWebSocketState.Closing

		if self._pollTask and coroutine.status(self._pollTask) ~= "dead" then
			task.cancel(self._pollTask)
		end
		self._pollTask = nil

		self.ConnectionState = EnumWebSocketState.Closed
		self._ClosedEvent:Fire()
	end
end

function MockWebSocketClient.SetReceiveEndpoint(self: MockWebSocketClientPrivate, endpoint: string)
	self._receiveEndpoint = endpoint
end

function MockWebSocketClient.SetSendEndpoint(self: MockWebSocketClientPrivate, endpoint: string)
	self._sendEndpoint = endpoint
end

local MockWebSocketService = {}
MockWebSocketService.__index = MockWebSocketService

type MockWebSocketService = {
	CreateClient: (self: MockWebSocketService, uri: string) -> MockWebSocketClient,
}

-- =======================================================================================
-- THE SINGLETON PATTERN FIX IS IMPLEMENTED HERE
-- =======================================================================================

-- A private, module-level variable to hold the one and only client instance.
local sharedClientInstance: MockWebSocketClient? = nil

function MockWebSocketService.CreateClient(_: MockWebSocketService, uri: string)
	-- If a shared client already exists AND it's not in a closed/closing state,
	-- return the existing one immediately.
	if sharedClientInstance and sharedClientInstance.ConnectionState ~= EnumWebSocketState.Closed and sharedClientInstance.ConnectionState ~= EnumWebSocketState.Closing then
		return sharedClientInstance
	end

	-- If no client exists (or the old one was closed), create a new one.
	local newClient = MockWebSocketClient.new(uri)
	
	-- Store the newly created client as our single shared instance.
	sharedClientInstance = newClient
	
	-- When this client is closed, clear the shared instance so a new one can be made later.
	newClient.Closed:Once(function()
		if sharedClientInstance == newClient then
			sharedClientInstance = nil
		end
	end)
	
	return newClient
end

return MockWebSocketService