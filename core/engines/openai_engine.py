"""
OpenAI Engine for advanced text and image analysis.
"""
import os
from typing import Optional, List, Dict, Any
import openai

class OpenAIEngine:
    """Handles interactions with the OpenAI API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPEN_AI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Please set OPEN_AI_API_KEY environment variable.")
        self.client = openai.AsyncOpenAI(api_key=self.api_key)

    async def improve_ocr_text(self, ocr_text: str) -> str:
        """
        Uses GPT to correct and structure messy OCR output.

        Args:
            ocr_text: The raw text extracted by Tesseract.

        Returns:
            A cleaned and more coherent version of the text.
        """
        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that cleans up and corrects OCR text from a video game screenshot. The user will provide messy text, and you should return a corrected version, preserving line breaks and structure where possible. The game is a strategy game with leaderboards."
                    },
                    {
                        "role": "user",
                        "content": f"Here is the raw OCR text:\n\n{ocr_text}"
                    }
                ],
                temperature=0.2,
            )
            return response.choices[0].message.content or ocr_text
        except Exception:
            # If AI fails, return original text
            return ocr_text

    async def analyze_correction(
        self,
        image_url: str,
        initial_text: str,
        initial_data: Dict[str, Any],
        corrected_data: Dict[str, Any],
        few_shot_examples: List[Dict[str, Any]]
    ) -> tuple[str, str]:
        """
        Uses GPT-4 Vision to analyze why OCR might have failed and learn from the correction.

        Returns:
            A tuple containing the AI's analysis and the failure category.
        """
        categories = ["ocr_noise", "layout_shift", "regex_mismatch", "semantic_mislabel", "context_missing", "unknown"]
        prompt = (
            "You are an OCR analysis expert. Your goal is to understand why the initial OCR failed, classify the failure, and suggest improvements.\n\n"
            f"**Initial OCR Text:**\n```\n{initial_text}\n```\n\n"
            f"**Initial Extracted Data:**\n`{initial_data}`\n\n"
            f"**User's Corrected Data:**\n`{corrected_data}`\n\n"
            "**Analysis Tasks:**\n"
            "1.  **Classify Failure:** First, choose ONE category that best describes the root cause of the failure from this list: "
            f"`{', '.join(categories)}`. The category must be the first line of your response, like `failure_category: ocr_noise`.\n"
            "2.  **Root Cause Analysis:** What in the image likely caused the error? (e.g., blur, unusual font, background noise, number formatting)\n"
            "3.  **Correction Logic:** How does the user's input fix the error? Is it a simple typo or a misinterpretation?\n"
            "4.  **Future Improvement:** Based on this, suggest a specific improvement to the OCR parsing logic (e.g., a new regex, a preprocessing step, a better way to isolate the user's row).\n\n"
            "Provide a concise analysis addressing these points after the category line."
        )

        if few_shot_examples:
            prompt += "\n\nHere are some recent examples of other corrections for context:\n"
            for ex in few_shot_examples:
                prompt += f"- Image had initial rank '{ex['initial_rank']}' corrected to '{ex['corrected_rank']}'. Analysis: {ex.get('ai_analysis', 'N/A')}\n"

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url},
                            },
                        ],
                    }
                ],
                max_tokens=500,
            )
            content = response.choices[0].message.content or "failure_category: unknown\nAI analysis failed."
            
            # Extract category from the first line
            lines = content.split('\n')
            category_line = lines[0]
            analysis = "\n".join(lines[1:]).strip()

            if 'failure_category:' in category_line:
                category = category_line.split('failure_category:')[1].strip()
                if category not in categories:
                    category = "unknown"
            else:
                category = "unknown"
                analysis = content # If format is wrong, keep all content as analysis

            return analysis, category
        except Exception as e:
            return f"An error occurred during AI analysis: {e}", "unknown"

    async def analyze_screenshot_with_vision(
        self,
        image_url: str,
        prompt: str,
        fields_to_extract: List[str]
    ) -> Dict[str, Any]:
        """
        Uses GPT-4 Vision to analyze a screenshot and extract specific fields.

        Args:
            image_url: The URL of the screenshot to analyze.
            prompt: The specific prompt guiding the analysis.
            fields_to_extract: A list of keys to look for in the JSON response.

        Returns:
            A dictionary with the extracted data.
        """
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url,
                                },
                            },
                        ],
                    }
                ],
                max_tokens=300,
            )
            # Assuming the model returns a JSON string
            content = response.choices[0].message.content
            # Basic parsing of a potential JSON block
            import json
            json_match = content.find('{')
            if json_match != -1:
                json_str = content[json_match:]
                # Find closing brace
                brace_level = 0
                end_index = -1
                for i, char in enumerate(json_str):
                    if char == '{':
                        brace_level += 1
                    elif char == '}':
                        brace_level -= 1
                        if brace_level == 0:
                            end_index = i + 1
                            break
                if end_index != -1:
                    try:
                        return json.loads(json_str[:end_index])
                    except json.JSONDecodeError:
                        pass
            return {} # Return empty if no valid JSON found
        except Exception:
            return {}
