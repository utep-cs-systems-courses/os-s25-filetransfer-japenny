#! /usr/bin/env python3
import socket, sys, re, os, uuid

from archiver import Archiver

sys.path.append("../lib")
from lib import params

switchesVarDefaults = (
    (('-s', '--server'), 'server', "127.0.0.1:50001"),
    (('-f', '--files'), 'files', True),
    (('-?', '--usage'), "usage", False),
)

paramMap = params.parseParams(switchesVarDefaults)
server, fileListStr, usage = paramMap["server"], paramMap["files"], paramMap["usage"]

if usage or not fileListStr:
    print("You must provide file(s) using -f 'file1 file2 ...'")
    params.usage()

fileList = fileListStr.split()

# Archive the files
archiveName = f"archive_{uuid.uuid4().hex[:8]}.tar"
try:
    print(f"Archiving files {fileList} into {archiveName}")
    archiver = Archiver()
    archiver.archive(archiveName, fileList)
except Exception as e:
    print("Archiving failed:", e)
    sys.exit(1)

# Connect to server
try:
    serverHost, serverPort = re.split(":", server)
    serverPort = int(serverPort)
except:
    print("Invalid server format. Use host:port")
    sys.exit(1)

s = socket.create_connection((serverHost, serverPort))
print(f"Connected to server at {serverHost}:{serverPort}")

# Send metadata: archive name and size
fileSize = os.path.getsize(archiveName)
metadata = f"{archiveName}\n{fileSize}\n".encode()
s.sendall(metadata)

# Send archive content
fd_in = os.open(archiveName, os.O_RDONLY)
bytesSent = 0

try:
    while True:
        chunk = os.read(fd_in, 4096)
        if not chunk:
            break
        s.sendall(chunk)
        bytesSent += len(chunk)
        print(f"Sent {bytesSent}/{fileSize} bytes")
except Exception as e:
    print("Failed to send file to server:", e)
    sys.exit(1)
finally:
    os.close(fd_in)

print(f"\nSent archive '{archiveName}'")
s.shutdown(socket.SHUT_WR)

response = s.recv(1024).decode()
print("Server says:", response)
s.close()


