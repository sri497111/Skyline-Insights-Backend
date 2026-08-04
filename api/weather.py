from http.server import BaseHTTPRequestHandler
import urllib.parse, requests, os, json
from groq import Groq

class handler(BaseHTTPRequestHandler):
    def run_llm(self, data):
        try:
            if not data or (data.get('current_temp') is None and data.get('forecast_24h') is None and data.get('forecast') is None):
                raise Exception("No data provided")

            current_time = data.get('current_time', 'N/A')
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
            
            known_keys = {'current_time', 'current_temp', 'current_wind', 'feels_like', 'uv_index', 'tomorrow_condition', 'forecast_24h', 'forecast'}
            extra_data = {k: v for k, v in data.items() if k not in known_keys}
            additional = ", ".join([f"{k.replace('_', ' ').title()}: {v}" for k, v in extra_data.items()] if extra_data else "N/A")

            key = os.environ.get('API_KEY')
            if not key:
                raise Exception("API Key not passed in")
            
            prompt = f'''
            You are a precise, practical weather assistant. Output ONLY the raw final insights string. Do not output headers, markdown formatting, or introductory text.

            ### DATA INPUT
            - Current Time: {current_time}
            - Current Temperature: {current_temp}
            - Feels-Like Temperature: {feels_like}
            - Current Wind: {current_wind}
            - Current UV Index: {uv_index}
            - Tomorrow's Overall Condition: {tomorrow}
            - Today's Forecast: {forecast_str}
            - Additional Context: {additional}

            ### FORMATTING RULES FOR TEMPERATURES
            - ALWAYS write temperature values as the number followed immediately by '|d|' (e.g., '96|d|', '102|d|', '18|d|').
            - DO NOT use the word 'degrees', the symbol '°', or units like 'F' or 'C'. 

            ### OUTPUT REQUIREMENTS
            - Output EXACTLY 3 weather insights.
            - Use a practical, helpful tone. Provide common-sense advice (e.g., apply sunscreen, grab a jacket) rather than extreme emergency warnings.
            - Strict Format: Direct Action Title -- Descriptive Reason;
            - Separate each of the 3 insights with a semicolon (;).
            - LENGTH RULE: Each insight (Title + Body) MUST be between 100 and 140 characters long.
            - LOGIC RULE: Compare the Current Time to the Today's Forecast. If a weather event (like rain) is already happening or indicated in the nearest forecast block, advise on the current conditions rather than predicting when it will start.
            - ANTI-HALLUCINATION RULE: Base insights STRICTLY on the provided data. DO NOT advise bringing an umbrella or mention rain/precipitation unless "Rain", "Thunderstorm", or "Drizzle" is explicitly listed in the input data. If the forecast just says "Clouds", advise on overcast conditions, not rain.

            ### EXAMPLE OUTPUT
            Protect your skin -- High UV rays today mean you should definitely apply a layer of sunscreen before heading outside; Dress in layers -- Steady cloud cover throughout the day means temperatures might feel a bit cooler when the wind picks up; Stay hydrated -- Feels-like temperatures will be reaching 102|d| today so make sure to drink plenty of water and rest;

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
