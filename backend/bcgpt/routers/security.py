from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from bcgpt.utils import get_admin_user

router = APIRouter()


def _get_config_value(val):
    from bcgpt.config import PersistentConfig

    if isinstance(val, PersistentConfig):
        return val.value
    return val


class ScannerConfigForm(BaseModel):
    enabled: bool


class PIIScannerConfigForm(BaseModel):
    enabled: bool
    mask_mode: str


class ToxicityScannerConfigForm(BaseModel):
    enabled: bool
    custom_word_list: str


class LLMScannerConfigForm(BaseModel):
    enabled: bool
    model: str


class GuardrailConfigForm(BaseModel):
    enabled: bool
    model: str
    action: str


class CanaryTokenConfigForm(BaseModel):
    enabled: bool
    position: str


class SIEMWebhookConfigForm(BaseModel):
    enabled: bool
    url: str
    headers: str


class SecurityConfigForm(BaseModel):
    enabled: bool
    emergency_stop: bool
    shadow_mode: bool
    log_detections: bool
    prompt_injection: ScannerConfigForm
    jailbreak: ScannerConfigForm
    pii: PIIScannerConfigForm
    toxicity: ToxicityScannerConfigForm
    secrets: ScannerConfigForm
    output_filter: ScannerConfigForm
    conversation_scanning_enabled: bool
    conversation_threshold: str
    confidence_threshold: str
    ai_transparency_enabled: bool
    ai_notification_title: str
    ai_notification_message: str
    ai_disclaimer_text: str
    ai_response_label: str
    rate_limit_chat_enabled: bool
    rate_limit_chat_per_minute: int
    rate_limit_chat_per_hour: int
    rate_limit_chat_per_day: int
    scan_file_uploads: bool
    scan_web_results: bool
    llm_scanner: LLMScannerConfigForm
    guardrail: GuardrailConfigForm
    canary_tokens: CanaryTokenConfigForm
    siem_webhook: SIEMWebhookConfigForm


@router.get("/config")
async def get_security_config(request: Request, user=Depends(get_admin_user)):
    config = request.app.state.config
    return {
        "enabled": _get_config_value(config.SECURITY_SCANNER_ENABLED),
        "emergency_stop": _get_config_value(config.SECURITY_EMERGENCY_STOP),
        "shadow_mode": _get_config_value(config.SECURITY_SHADOW_MODE),
        "log_detections": _get_config_value(config.SECURITY_LOG_DETECTIONS),
        "prompt_injection": {
            "enabled": _get_config_value(config.SECURITY_PROMPT_INJECTION_ENABLED),
        },
        "jailbreak": {
            "enabled": _get_config_value(config.SECURITY_JAILBREAK_ENABLED),
        },
        "pii": {
            "enabled": _get_config_value(config.SECURITY_PII_ENABLED),
            "mask_mode": _get_config_value(config.SECURITY_PII_MASK_MODE),
        },
        "toxicity": {
            "enabled": _get_config_value(config.SECURITY_TOXICITY_ENABLED),
            "custom_word_list": _get_config_value(
                config.SECURITY_TOXICITY_CUSTOM_WORD_LIST
            ),
        },
        "secrets": {
            "enabled": _get_config_value(config.SECURITY_SECRETS_ENABLED),
        },
        "output_filter": {
            "enabled": _get_config_value(config.SECURITY_OUTPUT_FILTER_ENABLED),
        },
        "conversation_scanning_enabled": _get_config_value(
            config.SECURITY_CONVERSATION_SCANNING_ENABLED
        ),
        "conversation_threshold": _get_config_value(
            config.SECURITY_CONVERSATION_THRESHOLD
        ),
        "confidence_threshold": _get_config_value(config.SECURITY_CONFIDENCE_THRESHOLD),
        "ai_transparency_enabled": _get_config_value(config.AI_TRANSPARENCY_ENABLED),
        "ai_notification_title": _get_config_value(config.AI_NOTIFICATION_TITLE),
        "ai_notification_message": _get_config_value(config.AI_NOTIFICATION_MESSAGE),
        "ai_disclaimer_text": _get_config_value(config.AI_DISCLAIMER_TEXT),
        "ai_response_label": _get_config_value(config.AI_RESPONSE_LABEL),
        "rate_limit_chat_enabled": _get_config_value(config.RATE_LIMIT_CHAT_ENABLED),
        "rate_limit_chat_per_minute": _get_config_value(
            config.RATE_LIMIT_CHAT_PER_MINUTE
        ),
        "rate_limit_chat_per_hour": _get_config_value(config.RATE_LIMIT_CHAT_PER_HOUR),
        "rate_limit_chat_per_day": _get_config_value(config.RATE_LIMIT_CHAT_PER_DAY),
        "scan_file_uploads": _get_config_value(config.SECURITY_SCAN_FILE_UPLOADS),
        "scan_web_results": _get_config_value(config.SECURITY_SCAN_WEB_RESULTS),
        "llm_scanner": {
            "enabled": _get_config_value(config.SECURITY_LLM_SCANNER_ENABLED),
            "model": _get_config_value(config.SECURITY_LLM_SCANNER_MODEL),
        },
        "guardrail": {
            "enabled": _get_config_value(config.SECURITY_GUARDRAIL_ENABLED),
            "model": _get_config_value(config.SECURITY_GUARDRAIL_MODEL),
            "action": _get_config_value(config.SECURITY_GUARDRAIL_ACTION),
        },
        "canary_tokens": {
            "enabled": _get_config_value(config.SECURITY_CANARY_TOKENS_ENABLED),
            "position": _get_config_value(config.SECURITY_CANARY_TOKEN_POSITION),
        },
        "siem_webhook": {
            "enabled": _get_config_value(config.SECURITY_SIEM_WEBHOOK_ENABLED),
            "url": _get_config_value(config.SECURITY_SIEM_WEBHOOK_URL),
            "headers": _get_config_value(config.SECURITY_SIEM_WEBHOOK_HEADERS),
        },
    }


@router.post("/config/update")
async def update_security_config(
    request: Request, form_data: SecurityConfigForm, user=Depends(get_admin_user)
):
    config = request.app.state.config

    config.SECURITY_SCANNER_ENABLED = form_data.enabled
    config.SECURITY_EMERGENCY_STOP = form_data.emergency_stop
    config.SECURITY_SHADOW_MODE = form_data.shadow_mode
    config.SECURITY_LOG_DETECTIONS = form_data.log_detections

    config.SECURITY_PROMPT_INJECTION_ENABLED = form_data.prompt_injection.enabled
    config.SECURITY_JAILBREAK_ENABLED = form_data.jailbreak.enabled
    config.SECURITY_PII_ENABLED = form_data.pii.enabled
    config.SECURITY_PII_MASK_MODE = form_data.pii.mask_mode
    config.SECURITY_TOXICITY_ENABLED = form_data.toxicity.enabled
    config.SECURITY_TOXICITY_CUSTOM_WORD_LIST = form_data.toxicity.custom_word_list
    config.SECURITY_SECRETS_ENABLED = form_data.secrets.enabled
    config.SECURITY_OUTPUT_FILTER_ENABLED = form_data.output_filter.enabled

    config.SECURITY_CONVERSATION_SCANNING_ENABLED = (
        form_data.conversation_scanning_enabled
    )
    config.SECURITY_CONVERSATION_THRESHOLD = form_data.conversation_threshold
    config.SECURITY_CONFIDENCE_THRESHOLD = form_data.confidence_threshold

    config.SECURITY_SCAN_FILE_UPLOADS = form_data.scan_file_uploads
    config.SECURITY_SCAN_WEB_RESULTS = form_data.scan_web_results

    config.SECURITY_LLM_SCANNER_ENABLED = form_data.llm_scanner.enabled
    config.SECURITY_LLM_SCANNER_MODEL = form_data.llm_scanner.model

    config.SECURITY_GUARDRAIL_ENABLED = form_data.guardrail.enabled
    config.SECURITY_GUARDRAIL_MODEL = form_data.guardrail.model
    config.SECURITY_GUARDRAIL_ACTION = form_data.guardrail.action

    config.SECURITY_CANARY_TOKENS_ENABLED = form_data.canary_tokens.enabled
    config.SECURITY_CANARY_TOKEN_POSITION = form_data.canary_tokens.position

    config.SECURITY_SIEM_WEBHOOK_ENABLED = form_data.siem_webhook.enabled
    config.SECURITY_SIEM_WEBHOOK_URL = form_data.siem_webhook.url
    config.SECURITY_SIEM_WEBHOOK_HEADERS = form_data.siem_webhook.headers

    config.AI_TRANSPARENCY_ENABLED = form_data.ai_transparency_enabled
    config.AI_NOTIFICATION_TITLE = form_data.ai_notification_title
    config.AI_NOTIFICATION_MESSAGE = form_data.ai_notification_message
    config.AI_DISCLAIMER_TEXT = form_data.ai_disclaimer_text
    config.AI_RESPONSE_LABEL = form_data.ai_response_label

    config.RATE_LIMIT_CHAT_ENABLED = form_data.rate_limit_chat_enabled
    config.RATE_LIMIT_CHAT_PER_MINUTE = form_data.rate_limit_chat_per_minute
    config.RATE_LIMIT_CHAT_PER_HOUR = form_data.rate_limit_chat_per_hour
    config.RATE_LIMIT_CHAT_PER_DAY = form_data.rate_limit_chat_per_day

    return {
        "enabled": _get_config_value(config.SECURITY_SCANNER_ENABLED),
        "emergency_stop": _get_config_value(config.SECURITY_EMERGENCY_STOP),
        "shadow_mode": _get_config_value(config.SECURITY_SHADOW_MODE),
        "log_detections": _get_config_value(config.SECURITY_LOG_DETECTIONS),
        "prompt_injection": {
            "enabled": _get_config_value(config.SECURITY_PROMPT_INJECTION_ENABLED),
        },
        "jailbreak": {
            "enabled": _get_config_value(config.SECURITY_JAILBREAK_ENABLED),
        },
        "pii": {
            "enabled": _get_config_value(config.SECURITY_PII_ENABLED),
            "mask_mode": _get_config_value(config.SECURITY_PII_MASK_MODE),
        },
        "toxicity": {
            "enabled": _get_config_value(config.SECURITY_TOXICITY_ENABLED),
            "custom_word_list": _get_config_value(
                config.SECURITY_TOXICITY_CUSTOM_WORD_LIST
            ),
        },
        "secrets": {
            "enabled": _get_config_value(config.SECURITY_SECRETS_ENABLED),
        },
        "output_filter": {
            "enabled": _get_config_value(config.SECURITY_OUTPUT_FILTER_ENABLED),
        },
        "conversation_scanning_enabled": _get_config_value(
            config.SECURITY_CONVERSATION_SCANNING_ENABLED
        ),
        "conversation_threshold": _get_config_value(
            config.SECURITY_CONVERSATION_THRESHOLD
        ),
        "confidence_threshold": _get_config_value(config.SECURITY_CONFIDENCE_THRESHOLD),
        "ai_transparency_enabled": _get_config_value(config.AI_TRANSPARENCY_ENABLED),
        "ai_notification_title": _get_config_value(config.AI_NOTIFICATION_TITLE),
        "ai_notification_message": _get_config_value(config.AI_NOTIFICATION_MESSAGE),
        "ai_disclaimer_text": _get_config_value(config.AI_DISCLAIMER_TEXT),
        "ai_response_label": _get_config_value(config.AI_RESPONSE_LABEL),
        "rate_limit_chat_enabled": _get_config_value(config.RATE_LIMIT_CHAT_ENABLED),
        "rate_limit_chat_per_minute": _get_config_value(
            config.RATE_LIMIT_CHAT_PER_MINUTE
        ),
        "rate_limit_chat_per_hour": _get_config_value(config.RATE_LIMIT_CHAT_PER_HOUR),
        "rate_limit_chat_per_day": _get_config_value(config.RATE_LIMIT_CHAT_PER_DAY),
        "scan_file_uploads": _get_config_value(config.SECURITY_SCAN_FILE_UPLOADS),
        "scan_web_results": _get_config_value(config.SECURITY_SCAN_WEB_RESULTS),
        "llm_scanner": {
            "enabled": _get_config_value(config.SECURITY_LLM_SCANNER_ENABLED),
            "model": _get_config_value(config.SECURITY_LLM_SCANNER_MODEL),
        },
        "guardrail": {
            "enabled": _get_config_value(config.SECURITY_GUARDRAIL_ENABLED),
            "model": _get_config_value(config.SECURITY_GUARDRAIL_MODEL),
            "action": _get_config_value(config.SECURITY_GUARDRAIL_ACTION),
        },
        "canary_tokens": {
            "enabled": _get_config_value(config.SECURITY_CANARY_TOKENS_ENABLED),
            "position": _get_config_value(config.SECURITY_CANARY_TOKEN_POSITION),
        },
        "siem_webhook": {
            "enabled": _get_config_value(config.SECURITY_SIEM_WEBHOOK_ENABLED),
            "url": _get_config_value(config.SECURITY_SIEM_WEBHOOK_URL),
            "headers": _get_config_value(config.SECURITY_SIEM_WEBHOOK_HEADERS),
        },
    }
