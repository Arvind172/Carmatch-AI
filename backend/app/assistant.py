import json
import logging
import os

from sqlalchemy.orm import Session

from app.presenters import format_listing
from app.recommendations import Requirements, has_search_preferences, parse_requirements, rank_listings, search_listings
from app.schemas import AssistantRequest, AssistantResponse


SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_vehicles",
        "description": "Search the sample car database. Convert budgets to full currency units: INR 20 lakh is 2000000, and USD 35k is 35000. Use the selected country and leave unknown filters null.",
        "parameters": {
            "type": "object",
            "properties": {
                "country_code": {"type": ["string", "null"], "description": "ISO market code: IN or US"},
                "currency_code": {"type": ["string", "null"], "description": "INR for India or USD for the United States"},
                "max_budget": {"type": ["number", "null"], "description": "Maximum price in full currency units, not lakh shorthand"},
                "transmission": {"type": ["string", "null"], "description": "Requested transmission, such as Automatic or Manual"},
                "body_style": {"type": ["string", "null"], "description": "Requested body style, such as SUV, Sedan, or Hatchback"},
                "fuel_type": {"type": ["string", "null"], "description": "Requested fuel or power type"},
                "condition": {"type": ["string", "null"], "description": "New or Used, if requested"},
                "seating_capacity": {"type": ["integer", "null"], "description": "Minimum number of seats required"},
                "priorities": {"type": "array", "items": {"type": "string"}, "description": "Soft preferences such as mileage, safety, or low price"},
            },
            "required": ["country_code", "currency_code", "max_budget", "transmission", "body_style", "fuel_type", "condition", "seating_capacity", "priorities"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}
logger = logging.getLogger(__name__)


def find_matching_vehicles(db: Session, requirements: Requirements):
    listings = search_listings(db, requirements)
    ranked = rank_listings(listings, requirements)[:6]
    return [format_listing(listing, score, reasons) for listing, score, reasons in ranked]


def merge_tool_requirements(arguments: dict, request: AssistantRequest) -> Requirements:
    requirements = Requirements(**arguments)
    previous_requests = [turn.content for turn in request.history if turn.role == "user"][-3:]
    conversation = " ".join(previous_requests + [request.message])
    explicit = parse_requirements(conversation, request.country_code)

    for field in (
        "max_budget", "transmission", "body_style", "fuel_type", "condition",
        "seating_capacity",
    ):
        value = getattr(explicit, field)
        setattr(requirements, field, value)
    requirements.priorities = list(set(requirements.priorities or []) | set(explicit.priorities or []))
    requirements.country_code = request.country_code.upper()
    requirements.currency_code = "INR" if requirements.country_code == "IN" else "USD"
    return requirements


def fallback_answer(items, has_preferences: bool = True) -> str:
    if not items:
        return "I couldn't find a match in the sample catalog. Try changing your budget or one of the filters."
    if not has_preferences:
        return (
            "I don't have enough preferences to explain a personalized choice yet. "
            "These cards are simply the lowest-priced sample listings in this market. "
            "Tell me your budget, preferred body style, or fuel type and I'll narrow them down."
        )
    explanations = []
    for item in items[:3]:
        name = f"{item.vehicle.model_year} {item.vehicle.make} {item.vehicle.model}"
        reasons = "; ".join(item.match_reasons[:5]) or "matches your selected market"
        explanations.append(f"{name}: {reasons}")
    return "Why these cars came up: " + "; ".join(explanations) + ". Prices and listings are illustrative samples, not live offers."


def ask_assistant(db: Session, request: AssistantRequest) -> AssistantResponse:
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    api_key = os.getenv("OPENAI_API_KEY")
    if provider == "openai" and not api_key:
        previous_requests = [turn.content for turn in request.history if turn.role == "user"][-3:]
        full_request = " ".join(previous_requests + [request.message])
        requirements = parse_requirements(full_request, request.country_code)
        items = find_matching_vehicles(db, requirements)
        return AssistantResponse(answer=fallback_answer(items, has_search_preferences(requirements)), ai_enabled=False, items=items)

    try:
        from openai import OpenAI

        if provider == "ollama":
            client = OpenAI(
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                api_key="ollama",
            )
            model = os.getenv("OLLAMA_MODEL", "qwen3:4b-instruct")
        else:
            client = OpenAI(api_key=api_key)
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        messages = [
            {
                "role": "system",
                "content": f"You help people choose a car. Use the search_vehicles tool before recommending anything. Use recent conversation messages to understand follow-up requests. Search only the selected market ({request.country_code}). For each car, explain why it fits by referring to its returned match reasons and values. Keep the answer concise and conversational. Only state details explicitly present in the tool results. Do not add general knowledge, reputation claims, features, availability, or reasons that are not in those results. If a listing is marked as a sample, call it an illustrative sample listing. If the database returns no cars, say there were no results in this sample catalog, not that no cars exist in the market. If the user gave no preferences, say the results are only sorted by sample price and ask one useful follow-up question.",
            }
        ]
        messages.extend(turn.model_dump() for turn in request.history[-8:])
        messages.append({"role": "user", "content": request.message})

        tool_request = {
            "model": model,
            "messages": messages,
            "tools": [SEARCH_TOOL],
        }
        if provider == "openai":
            tool_request["tool_choice"] = "required"
            tool_request["parallel_tool_calls"] = False
        first_reply = client.chat.completions.create(**tool_request)
        tool_calls = first_reply.choices[0].message.tool_calls
        if not tool_calls:
            requirements = parse_requirements(request.message, request.country_code)
            items = find_matching_vehicles(db, requirements)
            return AssistantResponse(
                answer=fallback_answer(items, has_search_preferences(requirements)),
                ai_enabled=False,
                items=items,
            )

        tool_call = tool_calls[0]
        arguments = json.loads(tool_call.function.arguments)
        requirements = merge_tool_requirements(arguments, request)
        items = find_matching_vehicles(db, requirements)
        tool_results = [
            {
                "car": f"{item.vehicle.model_year} {item.vehicle.make} {item.vehicle.model}",
                "price": str(item.price),
                "currency": item.currency_code,
                "fuel": item.variant.fuel_type,
                "transmission": item.variant.transmission,
                "seats": item.variant.seating_capacity,
                "reasons": item.match_reasons,
                "sample_listing": item.is_sample,
            }
            for item in items
        ]

        messages.append(first_reply.choices[0].message.model_dump(exclude_none=True))
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(tool_results),
        })
        final_reply = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
        )
        answer = final_reply.choices[0].message.content or fallback_answer(items)
        return AssistantResponse(answer=answer, ai_enabled=True, items=items)
    except Exception:
        logger.exception("Assistant request failed; using the local search parser")
        previous_requests = [turn.content for turn in request.history if turn.role == "user"][-3:]
        query = " ".join(previous_requests + [request.message])
        requirements = parse_requirements(query, request.country_code)
        items = find_matching_vehicles(db, requirements)
        return AssistantResponse(answer=fallback_answer(items, has_search_preferences(requirements)), ai_enabled=False, items=items)
