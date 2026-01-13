import time
import hashlib
import json

BLOCK_REWARD = 50
COINBASE_MATURITY = 2


def sha256(data):
    return hashlib.sha256(data.encode()).hexdigest()


class Transaction:
    def __init__(self, inputs, outputs, signature=None, pubkey=None):
        self.inputs = inputs      # list of (txid, index)
        self.outputs = outputs    # list of (address, amount)
        self.signature = signature
        self.pubkey = pubkey

    def to_dict(self):
        return {
            "inputs": self.inputs,
            "outputs": self.outputs,
            "signature": self.signature,
            "pubkey": self.pubkey
        }

    def txid(self):
        return sha256(json.dumps(self.to_dict(), sort_keys=True))


class Block:
    def __init__(self, index, prev_hash, transactions, timestamp=None, nonce=0):
        self.index = index
        self.prev_hash = prev_hash
        self.transactions = transactions
        self.timestamp = timestamp or time.time()
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        block_string = json.dumps({
            "index": self.index,
            "prev_hash": self.prev_hash,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "timestamp": self.timestamp,
            "nonce": self.nonce
        }, sort_keys=True)
        return sha256(block_string)

    def mine(self, difficulty=3):
        target = "0" * difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.calculate_hash()


class OMChain:
    def __init__(self):
        self.chain = []
        self.utxo = {}  # txid:index -> {address, amount, height}
        self.difficulty = 4
        self.genesis()

    def genesis(self):
        genesis = Block(0, "0" * 64, [], int(time.time()), 0)
        genesis.hash = genesis.compute_hash()
        self.chain.append(genesis)

    def add_block(self, block):
        # Verify previous hash
        if block.prev_hash != self.chain[-1].hash:
            print("❌ Invalid previous hash")
            return False

        # Verify PoW
        if not block.hash.startswith("0" * self.difficulty):
            print("❌ Invalid PoW")
            return False

        height = len(self.chain)

        # Process transactions
        for tx in block.transactions:
            txid = tx.txid()

            # Remove spent inputs
            for txin in tx.inputs:
                key = f"{txin[0]}:{txin[1]}"
                if key in self.utxo:
                    del self.utxo[key]

            # Add new outputs
            for idx, out in enumerate(tx.outputs):
                self.utxo[f"{txid}:{idx}"] = {
                    "address": out[0],
                    "amount": out[1],
                    "height": height
                }

        self.chain.append(block)
        return True

    def get_balance(self, address):
        balance = 0
        height = len(self.chain)

        for u in self.utxo.values():
            if u["address"] == address:
                # Coinbase maturity = 2 blocks
                if height - u["height"] >= 2:
                    balance += u["amount"]

        return balance
        