from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from web3 import Web3
from web3.exceptions import Web3Exception  # type: ignore

from .config import settings

logger = logging.getLogger("slh.blockchain")


class OnchainConfigError(RuntimeError):
    """שגיאה בקונפיגורציה של ארנק קהילתי / RPC."""


# ABI מינימלי לפונקציית transfer של טוקן ERC-20 (BEP-20 תואם)
MINIMAL_ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    }
]


def _get_web3() -> Web3:
    if not settings.BSC_RPC_URL:
        raise OnchainConfigError("BSC_RPC_URL is not configured")
    w3 = Web3(Web3.HTTPProvider(settings.BSC_RPC_URL))
    if not w3.is_connected():
        raise OnchainConfigError("Failed to connect to BSC RPC node")
    return w3


def send_slh_bsc_onchain(to_address: str, amount_slh: float) -> str:
    """שולח SLH (BEP-20) מארנק קהילתי לכתובת יעד.

    משתמש בנתונים הבאים מ-ENV:
      * SLH_TOKEN_ADDRESS
      * SLH_TOKEN_DECIMALS
      * COMMUNITY_HOT_WALLET_ADDRESS
      * COMMUNITY_HOT_WALLET_PRIVATE_KEY

    מחזיר tx_hash בתצורת hex.
    """

    if not settings.SLH_TOKEN_ADDRESS:
        raise OnchainConfigError("SLH_TOKEN_ADDRESS is not configured")
    if not settings.COMMUNITY_HOT_WALLET_ADDRESS or not settings.COMMUNITY_HOT_WALLET_PRIVATE_KEY:
        raise OnchainConfigError("COMMUNITY_HOT_WALLET_ADDRESS / PRIVATE_KEY are not configured")

    w3 = _get_web3()
    token_address = Web3.to_checksum_address(settings.SLH_TOKEN_ADDRESS)
    from_address = Web3.to_checksum_address(settings.COMMUNITY_HOT_WALLET_ADDRESS)
    to_address_cs = Web3.to_checksum_address(to_address)

    contract = w3.eth.contract(address=token_address, abi=MINIMAL_ERC20_ABI)

    decimals = int(settings.SLH_TOKEN_DECIMALS or 18)
    amount_wei = int(Decimal(str(amount_slh)) * (10 ** decimals))

    nonce = w3.eth.get_transaction_count(from_address)
    gas_price = w3.eth.gas_price

    tx = contract.functions.transfer(to_address_cs, amount_wei).build_transaction(
        {
            "from": from_address,
            "nonce": nonce,
            "gasPrice": gas_price,
        }
    )

    # הערכת גז
    try:
        gas_estimate = w3.eth.estimate_gas(tx)
    except Web3Exception as exc:  # type: ignore
        logger.warning("Failed to estimate gas: %s", exc)
        gas_estimate = 200_000

    tx.update({"gas": gas_estimate})

    signed = w3.eth.account.sign_transaction(
        tx,
        private_key=settings.COMMUNITY_HOT_WALLET_PRIVATE_KEY,
    )
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    tx_hex = tx_hash.hex()
    logger.info("Sent SLH on-chain: to=%s amount=%s tx=%s", to_address_cs, amount_slh, tx_hex)
    return tx_hex
