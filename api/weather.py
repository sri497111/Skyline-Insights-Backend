from http.server import BaseHTTPRequestHandler
import urllib.parse, requests, os, json
from groq import Groq

class handler(BaseHTTPRequestHandler):
    def run_llm(self, data):
        try:
            current_temp = data.get('current_temp', 'N/A')
            current_wind = data.get('current_wind', 'N/A')
            feels_like = data.get('feels_like', 'N/A')
            uv_index = data.get('uv_index', 'N/A')
            tomorrow = data.get('tomorrow_condition', 'N/A')

            forecast_list = data.get('forecast_24h', data.get('forecast', []))
            if isinstance(forecast_list, str):
                try:
                    forecast_list = json.loads(forecast_list)
                except Exception:
                    forecast_list = []

            forecast_str = ", ".join([
                f"{item[0]}: {item[2]} {item[1].title()}"
                for item in forecast_list if isinstance(item, list) and len(item) == 3
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

            ### FALLBACK RULE
            - IF data inputs are missing or marked 'N/A', DO NOT invent, hallucinate, or make up weather metrics. Output: "Insufficient weather data provided -- Unable to generate accurate daily insights;" repeated or structured as needed.

            ### OUTPUT REQUIREMENTS
            - Output EXACTLY 3 weather insights based strictly on provided data.
            - Strict Format: Direct Action Title -- Descriptive Reason;
            - Separate each of the 3 insights with a semicolon (;).
            - LENGTH RULE: Each insight (Title + Body) MUST be between 100 and 140 characters long.

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

            retrieved = completion.choices[0].message.content.strip()

            return retrieved

        except Exception as e:
            print(e)

    def send_json(self, code, payload):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode('utf-8'))
    
    def do_GET(self):
        try:
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            data = {k: v[0] for k, v in params.items()}
            insights = self.run_llm(data)
            self.send_json(200, {'status': 'success', 'insights': insights})
        except Exception as e:
            self.send_json(500, {'status': 'error', 'error': str(e)})
    
    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length'), 0)
            post_data = self.rfile.read(length)
            data = json.loads(post_data.decode('utf-8'))
            insights = self.run_llm(data)
            self.send_json(200, {'status': 'success', 'insights': insights})
        except Exception as e:
            self.send_json(500, {'status': 'error', 'error': str(e)})