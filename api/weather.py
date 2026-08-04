from http.server import BaseHTTPRequestHandler
import urllib.parse, requests, os, json
from groq import Groq

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.encode('utf-8'))

            current_temp = data.get('current_temp', 'N/A')
            current_wind = data.get('current_wind', 'N/A')
            feels_like = data.get('feels_like', 'N/A')
            uv_index = data.get('uv_index', 'N/A')
            tomorrow = data.get('tomorrow_condition', 'N/A')

            forecast_list = data.get('forecast', [])
            forecast_str = ", ".join([
                f"{item[0]}: {item[2]} {item[1].title()}"
                for item in forecast_list if len(item) >= 3
            ]) if forecast_list else "N/A"

            known_keys = {'current_temp', 'current_wind', 'feels_like', 'uv_index', 'tomorrow_condition', 'forecast'}
            extra_data = {k: v for k, v in data.items() if k not in known_keys}
            additional = ", ".join([f"{k.replace('_', ' ').title()}: {v}" for k, v in extra_data.items()] if extra_data else "N/A")


            key = os.environ.get('API_KEY')
            if not key:
                raise Exception("API Key not passed in")
            
            prompt = f'''
            You are a precise weather assistant. Output ONLY the raw final insights string. Do not output headers, markdown formatting, or introductory text.

            ### DATA INPUT
            - Current Temperature: {current_temp}
            - Feels-Like Temperature: {feels_like}
            - Current Wind: {current_wind}
            - Current UV Index: {uv_index}
            - Tomorrow's Condition: {tomorrow}
            - 24-Hour Forecast: {forecast_str}
            - Additional Context: {additional}

            ### EXTRA
            - Do not always expect additional context. If it is not provided, simply ignore it if it is empty or isn't really important or relevant.

            ### OUTPUT REQUIREMENTS
            - Output EXACTLY 3 weather insights.
            - Strict Format: Direct Action Title -- Descriptive Reason;
            - Separate each of the 3 insights with a semicolon (;).
            - LENGTH RULE: Each insight (Title + Body) MUST be between 100 and 140 characters long.

            ### EXAMPLE OUTPUT
            Protect your skin -- UV is currently extreme, so limit direct sun exposure and seek shade during peak hours; Bring an umbrella -- light showers are expected to begin around noon and continue throughout the evening; Layer up wisely -- cooler air and shifting winds will cause temperatures to drop sharply after sunset;

            ### RESPONSE:
                        
            '''

            client = Groq(api_key=key)

            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.4,
                max_tokens=200,
            )

            insights = completion.choices[0].message.content.strip()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()

            response_payload = {"status": "success", "insights": insights}
            self.wfile.write(json.dumps(response_payload).encode('utf-8'))

        except Exception as e:
            print(f"Backend Crash - {str(e)}")
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))