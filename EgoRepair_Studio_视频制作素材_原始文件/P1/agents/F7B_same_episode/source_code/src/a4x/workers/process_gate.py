"""Do not exec actual worker until immutable ownership receipt has been persisted."""
import json,os,sys
fd=int(sys.argv[1]);command=json.loads(sys.argv[2]);byte=os.read(fd,1);os.close(fd)
if byte!=b'R':raise SystemExit(4)
os.execv(command[0],command)
