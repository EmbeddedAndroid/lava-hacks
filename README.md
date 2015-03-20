# lava-hacks
a series of useful cli utilities for LAVA server interactions

```
$ cat $HOME/.lavarc
[linaro]
server: http://lava-server/RPC2
username: <user>
token: <auth-token>

usage: ./stream-lava-log.py --username <lava username> --token <lava token> --server <http://lava-server/RPC2> --job <lava job id>
usage: ./stream-lava-log.py --section linaro --job <lava job id>

# Override config settings on the command line
usage: ./stream-lava-log.py --section linaro --token <lava token> --job <lava job id>
```
