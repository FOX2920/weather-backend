import requests
import google.generativeai as genai
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

# Configuration
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)
API_KEY = os.getenv('API_KEY')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

app = Flask(__name__)
CORS(app)

def fetch_weather_data(api_key, city):
    current_url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric'
    current_response = requests.get(current_url)
    current_data = current_response.json()

    if current_response.status_code == 200:
        avg_temperature = round(current_data['main']['temp'], 2)
        wind_speed = current_data['wind']['speed']
        humidity = current_data['main']['humidity']
        weather_data = {
            'avg_temperature': avg_temperature,
            'wind_speed': wind_speed,
            'humidity': humidity
        }
        return weather_data
    else:
        print("Failed to retrieve current weather data:", current_data)
        return None

def generate_weather_email_gemini(city, weather_data):
    prompt = f"""
    You are a weather assistant. Your task is to write a detailed and friendly weather update email based on the provided weather data.

    Here is the weather data for {city}:

    Today's Weather:
    - Average Temperature: {weather_data['avg_temperature']}°C
    - Wind Speed: {weather_data['wind_speed']} m/s
    - Humidity: {weather_data['humidity']}%

    Please provide a detailed and friendly email based on the above data.
    """
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(prompt)
    return response.text

def send_email(to_email, subject, body):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")

@app.route('/weather_mail', methods=['GET'])
def get_weather_report():
    city = request.args.get('city')
    email = request.args.get('email')
    if not city or not email:
        return jsonify({'error': 'City name and email are required'}), 400
    
    weather_data = fetch_weather_data(API_KEY, city)
    
    if weather_data:
        email_content = generate_weather_email_gemini(city, weather_data)
        send_email(email, f"Weather Report for {city}", email_content)
        return jsonify({'message': 'Email sent successfully'})
    else:
        return jsonify({'error': 'Failed to retrieve weather data'}), 500

@app.route('/api/weather', methods=['GET'])
def get_weather():
    latitude = request.args.get('lat')
    longitude = request.args.get('lon')
    city_name = request.args.get('city')

    if not city_name and (not latitude or not longitude):
        return jsonify({"error": "Please provide either city name or latitude and longitude"}), 400

    if city_name and not (latitude and longitude):
        # Get coordinates from city name
        geo_url = f"https://api.openweathermap.org/geo/1.0/direct?q={city_name}&limit=1&appid={API_KEY}"
        geo_response = requests.get(geo_url)
        if geo_response.status_code != 200:
            return jsonify({"error": "Failed to fetch coordinates"}), 500
        geo_data = geo_response.json()
        if not geo_data:
            return jsonify({"error": "City not found"}), 404
        latitude = geo_data[0]['lat']
        longitude = geo_data[0]['lon']
        city_name = geo_data[0]['name']

    # Fetch weather data
    weather_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={latitude}&lon={longitude}&appid={API_KEY}"
    weather_response = requests.get(weather_url)
    if weather_response.status_code != 200:
        return jsonify({"error": "Failed to fetch weather data"}), 500
    
    weather_data = weather_response.json()

    # Process weather data
    unique_forecast_days = []
    five_days_forecast = []
    for forecast in weather_data['list']:
        forecast_date = datetime.fromtimestamp(forecast['dt']).date()
        if forecast_date not in unique_forecast_days and len(unique_forecast_days) < 5:
            unique_forecast_days.append(forecast_date)
            five_days_forecast.append(forecast)

    result = {
        "cityName": city_name,
        "forecast": five_days_forecast,
        "timestamp": datetime.now().isoformat()
    }

    return jsonify(result)

@app.route('/api/reverse-geo', methods=['GET'])
def reverse_geocode():
    latitude = request.args.get('lat')
    longitude = request.args.get('lon')

    if not latitude or not longitude:
        return jsonify({"error": "Please provide both latitude and longitude"}), 400

    url = f"https://api.openweathermap.org/geo/1.0/reverse?lat={latitude}&lon={longitude}&limit=1&appid={API_KEY}"
    response = requests.get(url)
    if response.status_code != 200:
        return jsonify({"error": "Failed to fetch city name"}), 500
    
    data = response.json()
    if not data:
        return jsonify({"error": "Location not found"}), 404

    return jsonify({"name": data[0]['name']})

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=True, port=port, use_reloader=False)
