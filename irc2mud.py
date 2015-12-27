from sys import argv
import logging
import asyncio
#logging.basicConfig(level=logging.DEBUG)

BINDHOST = '127.0.0.1'
BINDPORT = 6667

MUDHOST = argv[1]
MUDPORT = int(argv[2])

class MUDClientProtocol(asyncio.Protocol):
    def __init__(self):
        self.loop = loop
        
        self.last_bold = ""
        self.handling_contents = False
        self.contents = []

    def connection_made(self, transport):
        print("Connection made")
        self.transport = transport

    def data_received(self, data):
        #print('*** Data received: {!r}'.format(data))
        lines = data.decode('ascii', 'replace').rstrip('\r\n').split('\r\n')
        if not (len(lines) == 1 and not lines[0].strip()):
            for line in lines:
                name = "*"
                message = line.replace('[0m', '\x02').replace('[1m', '\x02')
                if len(line.split()) >= 3 and line.split(" ")[1] == "says,":
                    name = line.split(' ')[0]
                    message = line.split('"', 1)[1][:-1]
                    
                self.server.message(message, name=name)
                
                if message.startswith('\x02'):
                    if self.handling_contents:
                        self.contents.append(message.strip('\x02'))
                    else:
                        self.last_bold = message
                elif message == 'Contents:':
                    self.handling_contents = True
                    self.contents = []
                elif message == 'Obvious exits:':
                    if not handling_contents:
                        contents = []
                    self.handling_contents = False
                    self.server.topic(self.last_bold)
                    self.server.names(self.contents)
                elif message.startswith("Use connect <name> <password>"):
                    if self.server.muduser:
                        self.send('connect {} {}'.format(self.server.muduser, self.server.mudpassword))
                    
                    
    
    def connection_lost(self, exc):
        print('MUDClient: The server closed the connection')
        self.loop.stop()
    
    def send(self, message):
        self.transport.write(message.encode('ascii')+b'\r\n')


class IRCServerClientProtocol(asyncio.Protocol):
    def connection_made(self, transport):
        peername = transport.get_extra_info('peername')
        print('Connection from {}'.format(peername))
        self.transport = transport
        
        self.client = None
        
        self.buffer = b""
        
        self.muduser = None
        self.mudpassword = None
        
        self.nick = None
        self.user = None
        self.fullname = None
        self.serverhost = BINDHOST
        
        self.channel = "#"
        

    def data_received(self, data):
        message = data
        self.buffer += message
        
        for line in self.buffer.split(b'\n'):
            if not line: continue
            if not line.endswith(b'\r'):
                break
            self._parse(line.rstrip(b'\r'))
            line = b""
        self.buffer = line

        #self.transport.close()
    
    def _parse(self, line):
        line = line.decode('utf-8', 'replace')
        print("RECV: "+line)
        message = None
        if " :" in line:
            command, message = line.split(' :', 1)
        else:
            command = line
        command, *arguments = command.split()
        if command == "PASS":
            self.muduser, self.mudpassword = arguments[0].split(':')
            if self.client:
                self.client.send('connect {} {}'.format(self.muduser, self.mudpassword))
        elif command == "NICK":
            self.nick = arguments[0]
        elif command == "USER":
            self.user = arguments[0]
            self.serverhost = arguments[2]
            self.fullname = message
            self._send("001", self.nick, ":Welcome to irc2mud!")
            self._send("375", self.nick, ":MoTD goes here.")
            self._send("JOIN", self.channel, "*", source=self.nick+"!"+self.user+"@x")
            self._send("366", self.channel, ":End of /NAMES list")
            self._send("324", self.channel, "+t")
            
            asyncio.Task(self.connect_client())
            
        elif command == "PART":
            if arguments[0] == self.channel:
                self._send("JOIN", self.channel, "*", source=self.nick+"!"+self.user+"@x")
        elif command == "PRIVMSG":
            self.client.send(message)
        else:
            if self.nick and self.user:
                self._send("421", self.nick, command, ":Unknown command")
        
    def _send(self, command, *arguments, source=None):
        if not source: source = self.serverhost
        packet = ":{} {}".format(source, command)
        if arguments:
            last = False
            for argument in arguments:
                if last:
                    print("ERROR: argument following last argument")
                if argument.startswith(":"):
                    last = True
                if " " in argument and not last:
                    print("ERROR: space before final argument")
                packet += " "+str(argument)
        
        print("SEND: "+packet)
        packet += "\r\n"
        
        self.transport.write(packet.encode('utf-8'))
    
    def message(self, message, name="*"):
        self._send("PRIVMSG", self.channel, ":"+message, source=name+"!*@*")
        
    def topic(self, message, name="*"):
        self._send("TOPIC", self.channel, ":"+message, source=name+"!*@*")
        
    def names(self, users):
        self._send("353", self.nick, '=', self.channel, ":"+" ".join(user.replace(' ', '\xa0') for user in users))
        self._send("366", self.nick, self.channel, ":End of /NAMES list.")
    
    @asyncio.coroutine
    def connect_client(self):
        print("will connect client")
        protocol, self.client = yield from loop.create_connection(MUDClientProtocol, MUDHOST, MUDPORT)
        self.client.server = self
        print("connected client?")

loop = asyncio.get_event_loop()
#loop.set_debug(True)
server_coro = loop.create_server(IRCServerClientProtocol, BINDHOST, BINDPORT)
server = loop.run_until_complete(server_coro)

# Serve requests until Ctrl+C is pressed
print('Serving on {}'.format(server.sockets[0].getsockname()))
try:
    loop.run_forever()
except KeyboardInterrupt:
    pass

# Close the server
server.close()
loop.run_until_complete(server.wait_closed())
loop.close()
