import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class PaymentService:
    """Mobile Money payment service for Cameroon (MTN MoMo, Orange Money).

    Supports mock mode for development and real API integration via REST.
    """

    def __init__(self, firebase_service=None):
        self.fb = firebase_service
        self._providers = {
            'mtn': {'name': 'MTN MoMo', 'enabled': False, 'api_key': '', 'api_secret': '', 'collection_primary_key': ''},
            'orange': {'name': 'Orange Money', 'enabled': False, 'api_key': '', 'api_secret': '', 'merchant_code': ''},
        }

    def configure_provider(self, provider: str, **kwargs):
        if provider in self._providers:
            self._providers[provider].update(kwargs)
            self._providers[provider]['enabled'] = True
            logger.info(f"Payment provider configured: {provider}")

    def initiate_payment(self, provider: str, phone: str, amount: int,
                         reference: str = '', description: str = '',
                         institution_id: str = '') -> Dict[str, Any]:
        result = {
            'transaction_id': str(uuid.uuid4()),
            'provider': provider,
            'phone': phone,
            'amount': amount,
            'reference': reference or str(uuid.uuid4()),
            'status': 'pending',
            'institution_id': institution_id,
            'timestamp': datetime.utcnow().isoformat(),
        }
        try:
            if provider == 'mtn':
                return self._initiate_mtn(result)
            elif provider == 'orange':
                return self._initiate_orange(result)
            else:
                return self._initiate_mock(result)
        except Exception as e:
            logger.error(f"Payment initiation failed: {e}")
            result['status'] = 'failed'
            result['error'] = str(e)
            return result

    def confirm_payment(self, transaction_id: str, provider_ref: str = '') -> Dict[str, Any]:
        result = {
            'transaction_id': transaction_id,
            'provider_reference': provider_ref,
            'status': 'confirmed',
            'confirmed_at': datetime.utcnow().isoformat(),
        }
        if self.fb:
            txns = self.fb.query_documents('payment_transactions',
                                           filters=[{'field': 'id', 'value': transaction_id}])
            if txns:
                txn = txns[0]
                self.fb.update_document('payment_transactions', transaction_id, {
                    'status': 'completed',
                    'provider_reference': provider_ref,
                    'confirmed_at': result['confirmed_at'],
                    'updated_at': datetime.utcnow().isoformat(),
                })
                result['amount'] = txn.get('amount', 0)
                result['phone'] = txn.get('phone', '')
        return result

    def _initiate_mock(self, result: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[MOCK PAYMENT] Provider: {result['provider']} | "
                    f"Phone: {result['phone']} | Amount: {result['amount']} | "
                    f"Ref: {result['reference']}")
        result['status'] = 'completed'
        result['provider_reference'] = f'mock_ref_{uuid.uuid4().hex[:8]}'
        result['message_en'] = 'Payment completed successfully (mock)'
        result['message_fr'] = 'Paiement effectué avec succès (simulation)'
        self._save_transaction(result)
        return result

    def _initiate_mtn(self, result: Dict[str, Any]) -> Dict[str, Any]:
        cfg = self._providers.get('mtn', {})
        if not cfg.get('collection_primary_key'):
            return self._initiate_mock(result)
        try:
            import requests
            resp = requests.post(
                'https://sandbox.momodeveloper.mtn.com/collection/v1_0/requesttopay',
                headers={
                    'X-Reference-Id': result['reference'],
                    'X-Target-Environment': 'sandbox',
                    'Content-Type': 'application/json',
                    'Ocp-Apim-Subscription-Key': cfg.get('collection_primary_key', ''),
                },
                json={
                    'amount': str(result['amount']),
                    'currency': 'EUR',
                    'externalId': result['reference'],
                    'payer': {'partyIdType': 'MSISDN', 'partyId': result['phone']},
                    'payerMessage': f'Payment {result["reference"]}',
                    'payeeNote': f'Attendrix {result["reference"]}',
                },
                timeout=30,
            )
            if resp.status_code in (200, 201, 202):
                result['status'] = 'pending'
                result['provider_reference'] = resp.headers.get('X-Reference-Id', '')
            else:
                result['status'] = 'failed'
                result['error'] = f"MTN API error: {resp.status_code}"
        except ImportError:
            return self._initiate_mock(result)
        except Exception as e:
            logger.error(f"MTN MoMo error: {e}")
            result['status'] = 'failed'
            result['error'] = str(e)
        self._save_transaction(result)
        return result

    def _initiate_orange(self, result: Dict[str, Any]) -> Dict[str, Any]:
        cfg = self._providers.get('orange', {})
        if not cfg.get('merchant_code'):
            return self._initiate_mock(result)
        try:
            import requests
            resp = requests.post(
                'https://api.orange.com/orange-money-webpay/v1/webpayment',
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                json={
                    'merchant_key': cfg.get('merchant_code', ''),
                    'amount': str(result['amount']),
                    'currency': 'XAF',
                    'order_id': result['reference'],
                    'return_url': '',
                    'cancel_url': '',
                    'notif_url': '',
                    'lang': 'en',
                    'reference': result['reference'],
                },
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                result['status'] = 'pending'
                result['payment_url'] = data.get('payment_url', '')
                result['provider_reference'] = data.get('notif_token', '')
            else:
                result['status'] = 'failed'
                result['error'] = f"Orange API error: {resp.status_code}"
        except ImportError:
            return self._initiate_mock(result)
        except Exception as e:
            logger.error(f"Orange Money error: {e}")
            result['status'] = 'failed'
            result['error'] = str(e)
        self._save_transaction(result)
        return result

    def _save_transaction(self, result: Dict[str, Any]):
        if not self.fb:
            return
        try:
            self.fb.create_document('payment_transactions', {
                'id': result['transaction_id'],
                'institution_id': result.get('institution_id', ''),
                'provider': result['provider'],
                'phone': result['phone'],
                'amount': result['amount'],
                'amount_xaf': result['amount'],
                'reference': result.get('reference', ''),
                'status': result['status'],
                'provider_reference': result.get('provider_reference', ''),
                'error': result.get('error', ''),
                'message_en': result.get('message_en', ''),
                'message_fr': result.get('message_fr', ''),
                'created_at': result['timestamp'],
                'updated_at': datetime.utcnow().isoformat(),
            }, result['transaction_id'])
        except Exception as e:
            logger.error(f"Failed to save transaction: {e}")

    def get_provider_status(self) -> List[Dict[str, Any]]:
        return [
            {
                'id': 'mtn',
                'name': self._providers['mtn']['name'],
                'enabled': self._providers['mtn']['enabled'],
            },
            {
                'id': 'orange',
                'name': self._providers['orange']['name'],
                'enabled': self._providers['orange']['enabled'],
            },
        ]
