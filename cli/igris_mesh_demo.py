import asyncio
from pathlib import Path

from mesh.identity import generate_local_identity
from mesh.store import Peer, PeerStore
from mesh.gossip import Gossip


async def main() -> None:
    ident = generate_local_identity(Path(".igris/identity"))
    store = PeerStore(Path(".igris/peers.json"))
    gossip = Gossip()

    async def on_policy(channel, payload):
        print(f"[gossip] {channel} -> {payload}")

    gossip.subscribe("policy", on_policy)
    await gossip.publish("policy", {"device": ident.device_id, "hello": True})

    store.upsert(Peer(id=ident.device_id, host="127.0.0.1", port=0, last_seen=0))
    print("Peers:", list(store.list().keys()))


if __name__ == "__main__":
    asyncio.run(main())

