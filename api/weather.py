from http.server import BaseHTTPRequestHandler
import urllib.parse, os, json
from groq import Groq

class handler(BaseHTTPRequestHandler):
    def run_llm(self, data):
        if not data or (data.get('current_temp') is None and data.get('forecast_24h') is None and data.get('forecast') is None):
            raise Exception("No weather data provided in request payload")

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

        key = os.environ.get('API_KEY') or os.environ.get('GROQ_API_KEY')
        if not key:
            raise Exception("API_KEY environment variable is not configured on Vercel")

        prompt = f'''
        You are a precise, practical weather assistant. Output ONLY the raw final insights string. Do not output headers, markdown formatting, or introductory text.

        ### DATA INPUT
        - Current Time: {current_time}
        - Current Temp: {current_temp}
        - Feels Like: {feels_like}
        - Wind: {current_wind}
        - UV Index: {uv_index}
        - Tomorrow's Condition: {tomorrow}
        - Today's Forecast: {forecast_str}
        - Additional Context: {additional}

        ### TEMPERATURE RULES
        - DO NOT output exact temperature numbers (e.g., do not say "85" or "85 degrees").
        - Describe temperature naturally based on the data (e.g., "warm", "hot", "chilly", "freezing", "mild", "dry", "sweltering").

        ### OUTPUT REQUIREMENTS
        - Output EXACTLY 3 weather insights.
        - Strict Format: Direct Action Title -- Descriptive Reason;
        - Separate each of the 3 insights with a semicolon (;).
        - Keep each insight reasonably detailed (around 90 to 110 characters).

        ### STRICT ANTI-HALLUCINATION RULES
        - Generate insights based ONLY on the DATA INPUT.
        - IF UV Index is 0-2 or it is nighttime: NEVER mention sunscreen, sun, or UV rays.
        - IF forecast includes "Rain": You MUST talk about rain or wet conditions.
        - IF forecast is only "Clouds" (and NO rain): Talk about overcast conditions, do not invent rain.

        ### EXAMPLE OUTPUT
        Bundle up tight -- Freezing conditions and heavy snow mean you should wear a heavy winter coat outside; Drive with caution -- Icy roads and low visibility are expected today so take your time on the roads; Stay indoors -- High winds and blizzard conditions make it dangerous, so grab a blanket and stay warm;

        ### RESPONSE:
        '''

        client = Groq(api_key=key)

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=350,
        )

        message = completion.choices[0].message
        content = getattr(message, 'content', None)

        if not content:
            finish_reason = getattr(completion.choices[0], 'finish_reason', 'unknown')
            raise Exception(f"Model returned no content (finish_reason: {finish_reason})")

        return content.strip()

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
