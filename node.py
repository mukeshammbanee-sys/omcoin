import socket
import threading
import json
import sys
import hashlib
from ecdsa import SigningKey, SECP256k1, VerifyingKey
from mine import OMChain, Block, Transaction, BLOCK_REWARD


def sha256(data):
    return hashlib.sha256(data.encode()).hexdigest()


class Wallet:
    def __init__(self):
        self.sk = SigningKey.generate(curve=SECP256k1)
        self.vk = self.sk.verifying_key
        self.address = sha256(self.vk.to_string().hex())[:40]

    def sign(self, message):
        return self.sk.sign(message.encode()).hex()


class Node:
    def __init__(self, port):
        self.port = port
        self.chain = OMChain()
        self.wallet = Wallet()
        self.peers = []
        self.mempool = []

        print(f"🟢 Node running on 127.0.0.1:{port}")
        print(f"💳 Wallet address: {self.wallet.address}")

        threading.Thread(target=self.listen, daemon=True).start()
        self.cli()

    # ---------------- NETWORK ----------------

    def listen(self):
        s = socket.socket()
        s.bind(("127.0.0.1", self.port))
        s.listen()
        while True:
            conn, _ = s.accept()
            threading.Thread(target=self.handle_peer, args=(conn,), daemon=True).start()

    def handle_peer(self, conn):
        data = conn.recv(65536)
        msg = json.loads(data.decode())

        if msg["type"] == "block":
            b = msg["data"]
            block = Block(
                b["index"],
                b["prev_hash"],
                [Transaction(**tx) for tx in b["transactions"]],
                b["timestamp"],
                b["nonce"]
            )
            if self.chain.add_block(block):
                print("🔗 Block synced from peer")

        if msg["type"] == "tx":
            tx = Transaction(**msg["data"])
            self.mempool.append(tx)
            print("📨 Transaction received")

    def broadcast(self, msg):
        for p in self.peers:
            try:
                s = socket.socket()
                s.connect(p)
                s.send(json.dumps(msg).encode())
                s.close()
            except:
                pass

    # ---------------- MINING ----------------

    def mine(self):
        coinbase = Transaction([], [(self.wallet.address, BLOCK_REWARD)])
        txs = [coinbase] + self.mempool

        block = Block(
            len(self.chain.chain),
            self.chain.chain[-1].hash,
            txs
        )
        block.mine()
        self.chain.add_block(block)
        self.mempool.clear()

        print(f"⛏ Block {block.index} mined")

        self.broadcast({
            "type": "block",
            "data": {
                "index": block.index,
                "prev_hash": block.prev_hash,
                "transactions": [tx.to_dict() for tx in block.transactions],
                "timestamp": block.timestamp,
                "nonce": block.nonce
            }
        })

    # ---------------- TRANSACTION ----------------

    def create_transaction(self, to_addr, amount):
        utxos = []
        total = 0

        for k, u in self.chain.utxo.items():
            if u["address"] == self.wallet.address:
                if len(self.chain.chain) - u["height"] >= 2:
                    txid, idx = k.split(":")
                    utxos.append((txid, int(idx), u["amount"]))
                    total += u["amount"]
                    if total >= amount:
                        break

        if total < amount:
            print("❌ Insufficient or immature balance")
            return

        inputs = [(txid, idx) for txid, idx, _ in utxos]
        outputs = [(to_addr, amount)]

        change = total - amount
        if change > 0:
            outputs.append((self.wallet.address, change))

        tx = Transaction(inputs, outputs)
        msg = json.dumps(tx.to_dict(), sort_keys=True)
        tx.signature = self.wallet.sign(msg)
        tx.pubkey = self.wallet.vk.to_string().hex()

        self.mempool.append(tx)
        self.broadcast({"type": "tx", "data": tx.to_dict()})

        print("✅ Transaction created and broadcast")

    # ---------------- CLI ----------------

    def cli(self):
        print("Commands:")
        print(" wallet | balance | mine")
        print(" send <address> <amount>")
        print(" connect <ip> <port> | peers | exit")

        while True:
            cmd = input("> ").split()

            if cmd[0] == "wallet":
                print("Address:", self.wallet.address)

            elif cmd[0] == "balance":
                print("Balance:", self.chain.get_balance(self.wallet.address))

            elif cmd[0] == "mine":
                self.mine()

            elif cmd[0] == "send":
                self.create_transaction(cmd[1], int(cmd[2]))

            elif cmd[0] == "connect":
                peer = (cmd[1], int(cmd[2]))
                self.peers.append(peer)
                print(f"🔗 Connected to {peer[0]}:{peer[1]}")

            elif cmd[0] == "peers":
                print(self.peers)

            elif cmd[0] == "exit":
                sys.exit()


if __name__ == "__main__":
    port = int(sys.argv[1])
    Node(port)
    