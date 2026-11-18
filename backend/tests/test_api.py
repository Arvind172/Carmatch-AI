import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.recommendations import parse_requirements, rank_listings, search_listings


class CarmatchApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)

    def test_seeded_vehicles_and_detail(self):
        response = self.client.get("/api/vehicles?country_code=IN")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 6)
        listing_id = response.json()["items"][0]["id"]
        self.assertEqual(self.client.get(f"/api/vehicles/{listing_id}").status_code, 200)

    def test_search_filters_and_price_validation(self):
        response = self.client.get("/api/vehicles?country_code=US&body_style=SUV&condition=New")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(item["vehicle"]["body_style"] == "SUV" for item in response.json()["items"]))
        self.assertEqual(self.client.get("/api/vehicles?min_price=100&max_price=10").status_code, 422)

    def test_natural_language_recommendations(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.post("/api/recommendations", json={
                "query": "automatic SUV under ₹20 lakh for a family of five",
                "country_code": "IN",
            })
        self.assertEqual(response.status_code, 200)
        cars = response.json()["items"]
        self.assertTrue(cars)
        self.assertTrue(all(float(car["price"]) <= 2_000_000 for car in cars))
        self.assertTrue(all(car["variant"]["seating_capacity"] >= 5 for car in cars))

    def test_assistant_uses_database_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.post("/api/assistant", json={
                "message": "make it automatic",
                "country_code": "IN",
                "history": [{"role": "user", "content": "Find an SUV under ₹20 lakh for a family of five"}],
            })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ai_enabled"])
        self.assertTrue(response.json()["items"])
        self.assertIn("illustrative", response.json()["answer"])
        self.assertIn("why these cars came up", response.json()["answer"].lower())
        self.assertTrue(response.json()["items"][0]["match_reasons"])
        self.assertIn("under your ₹20 lakh budget", response.json()["answer"])
        self.assertIn("seats 5", response.json()["answer"].lower())

    def test_assistant_does_not_claim_a_personalized_match_without_preferences(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.post("/api/assistant", json={
                "message": "Show me some cars",
                "country_code": "IN",
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn("don't have enough preferences", response.json()["answer"])
        self.assertIn("lowest-priced sample listings", response.json()["answer"])

    def test_assistant_understands_budget_follow_up_without_currency_symbol(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.post("/api/assistant", json={
                "message": "15 laks budget",
                "country_code": "IN",
                "history": [{"role": "user", "content": "Show me a cheap car"}],
            })
        self.assertEqual(response.status_code, 200)
        prices = [float(car["price"]) for car in response.json()["items"]]
        self.assertTrue(prices)
        self.assertTrue(all(price <= 1_500_000 for price in prices))
        self.assertIn("₹15 lakh budget", response.json()["answer"])

    def test_assistant_uses_search_tool_when_ai_is_enabled(self):
        tool_arguments = '{"country_code":"IN","currency_code":"INR","max_budget":2000000,"transmission":"Automatic","body_style":"SUV","fuel_type":null,"condition":null,"seating_capacity":5,"priorities":[]}'
        tool_call = SimpleNamespace(id="call_search", function=SimpleNamespace(arguments=tool_arguments))
        assistant_message = Mock()
        assistant_message.tool_calls = [tool_call]
        assistant_message.model_dump.return_value = {"role": "assistant", "tool_calls": []}
        tool_response = SimpleNamespace(choices=[SimpleNamespace(message=assistant_message)])
        final_response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="The Kia Seltos is below your budget, has an automatic transmission, and seats five."))])
        openai = Mock()
        openai.return_value.chat.completions.create.side_effect = [tool_response, final_response]

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), patch("openai.OpenAI", openai):
            response = self.client.post("/api/assistant", json={"message": "Need an automatic family SUV under INR 20 lakh with seating for five", "country_code": "IN"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ai_enabled"])
        self.assertIn("seats five", response.json()["answer"])
        self.assertTrue(response.json()["items"])
        self.assertEqual(openai.return_value.chat.completions.create.call_count, 2)
        final_messages = openai.return_value.chat.completions.create.call_args_list[1].kwargs["messages"]
        tool_result = next(message["content"] for message in final_messages if message["role"] == "tool")
        self.assertIn("under your", tool_result)
        self.assertIn("SUV body style", tool_result)

    def test_assistant_can_use_local_ollama(self):
        tool_arguments = '{"country_code":"IN","currency_code":"INR","max_budget":null,"transmission":null,"body_style":"SUV","fuel_type":null,"condition":null,"seating_capacity":null,"priorities":[]}'
        tool_call = SimpleNamespace(id="call_search", function=SimpleNamespace(arguments=tool_arguments))
        assistant_message = Mock()
        assistant_message.tool_calls = [tool_call]
        assistant_message.model_dump.return_value = {"role": "assistant", "tool_calls": []}
        tool_response = SimpleNamespace(choices=[SimpleNamespace(message=assistant_message)])
        final_response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="I found sample SUVs in the India catalog."))])
        ollama = Mock()
        ollama.return_value.chat.completions.create.side_effect = [tool_response, final_response]

        settings = {
            "LLM_PROVIDER": "ollama",
            "OLLAMA_MODEL": "qwen3:4b-instruct",
            "OLLAMA_BASE_URL": "http://localhost:11434/v1",
        }
        with patch.dict(os.environ, settings, clear=True), patch("openai.OpenAI", ollama):
            response = self.client.post("/api/assistant", json={"message": "Find an SUV", "country_code": "IN"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ai_enabled"])
        self.assertEqual(ollama.call_args.kwargs["base_url"], settings["OLLAMA_BASE_URL"])
        first_request = ollama.return_value.chat.completions.create.call_args_list[0].kwargs
        self.assertEqual(first_request["model"], settings["OLLAMA_MODEL"])
        self.assertNotIn("tool_choice", first_request)

    def test_recommendation_quality_examples(self):
        examples = [
            ("hybrid SUV under $40k", "US", "RAV4"),
            ("electric sedan under $40k", "US", "Model 3"),
            ("used sedan in India", "IN", "City"),
        ]
        with SessionLocal() as db:
            for query, market, expected_model in examples:
                requirements = parse_requirements(query, market)
                ranked = rank_listings(search_listings(db, requirements), requirements)
                self.assertTrue(ranked)
                self.assertEqual(ranked[0][0].variant.vehicle.model, expected_model)

    def test_compare_and_save(self):
        cars = self.client.get("/api/vehicles?country_code=IN").json()["items"]
        ids = [car["id"] for car in cars[:2]]
        self.assertEqual(self.client.post("/api/compare", json={"listing_ids": ids}).status_code, 200)
        self.assertEqual(self.client.post(f"/api/saved/{ids[0]}").status_code, 201)
        self.assertIn(ids[0], [car["id"] for car in self.client.get("/api/saved").json()])
        self.assertEqual(self.client.delete(f"/api/saved/{ids[0]}").status_code, 204)


if __name__ == "__main__":
    unittest.main()
