from flask import Flask, request, jsonify
import requests
import json
import re
from datetime import datetime, timedelta
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pytz  # Asegúrate de instalar: pip install pytz

# Importaciones para Google Calendar API
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Crear la aplicación Flask (cambiar 'app' por 'application' para Passenger)
application = Flask(__name__)

# === CONFIGURACIÓN ===
META_ACCESS_TOKEN = os.environ.get('META_ACCESS_TOKEN') or 'temporal_token_placeholder'
META_PHONE_NUMBER_ID = os.environ.get('META_PHONE_NUMBER_ID') or '123456789012345'
META_VERIFY_TOKEN = os.environ.get('META_VERIFY_TOKEN') or 'milkiin_verify_token_2024'

# Variables para Google Calendar
GOOGLE_CALENDAR_CREDENTIALS_JSON = os.environ.get('GOOGLE_CALENDAR_CREDENTIALS')
GOOGLE_CALENDAR_ID = os.environ.get('GOOGLE_CALENDAR_ID')  # Debe ser el email del calendario
SCOPES = ['https://www.googleapis.com/auth/calendar.events']  # Sin espacios

# === CONFIGURACIÓN DE CORREO ELECTRÓNICO ===
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 465

# Zona horaria de México
mexico_tz = pytz.timezone('America/Mexico_City')

# === AUTENTICACIÓN Y SERVICIO DE CALENDAR ===
def get_calendar_service():
    """
    Inicializa el servicio de Google Calendar usando credenciales de cuenta de servicio.
    """
    try:
        if not GOOGLE_CALENDAR_CREDENTIALS_JSON:
            print("❌ GOOGLE_CALENDAR_CREDENTIALS_JSON no está definido.")
            return None

        info = json.loads(GOOGLE_CALENDAR_CREDENTIALS_JSON)
        credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        service = build('calendar', 'v3', credentials=credentials)
        return service
    except (json.JSONDecodeError, Exception) as e:
        print(f"❌ Error al cargar credenciales de Google Calendar: {e}")
        return None

# === ESTADO DE CONVERSACIÓN ===
user_state = {}
user_data_storage = {}

# === MENSAJES DEL BOT ===
WELCOME_MESSAGE = {
    "type": "text",
    "text": {
        "body": "👋 ¡Hola! Bienvenido(a) a Milkiin, donde cada paso en tu camino a la maternidad cuenta. ✨ Soy MilkiBot, tu asistente virtual.\n\n¿En qué te puedo apoyar hoy?\n\n1️⃣ Paciente de primera vez\n2️⃣ Paciente subsecuente\n3️⃣ Atención al cliente\n4️⃣ Facturación\n5️⃣ Envío de Resultados\n6️⃣ Dudas"
    }
}

SERVICIOS_PRIMERA_VEZ = {
    "type": "text",
    "text": {
        "body": "Selecciona el servicio de primera vez:\n1️⃣ Fertilidad\n2️⃣ Síndrome de Ovario Poliquístico\n3️⃣ Chequeo Anual\n4️⃣ Embarazo\n5️⃣ Otros"
    }
}

SERVICIOS_SUBSECUENTE = {
    "type": "text",
    "text": {
        "body": "Selecciona el servicio subsecuente:\n1️⃣ Fertilidad\n2️⃣ Síndrome de Ovario Poliquístico\n3️⃣ Chequeo Anual\n4️⃣ Embarazo\n5️⃣ Revisión de estudios\n6️⃣ Seguimiento folicular\n7️⃣ Otros"
    }
}

OTROS_OPCIONES = {
    "type": "text",
    "text": {
        "body": "Selecciona una opción:\n1️⃣ Espermabiopsia directa\n2️⃣ Ginecología Pediátrica y Adolescentes\n3️⃣ Hablar con América"
    }
}

ESPECIALISTAS = {
    "type": "text",
    "text": {
        "body": "Selecciona tu especialista:\n1️⃣ Dra. Mónica Olavarría\n2️⃣ Dra. Graciela Guadarrama\n3️⃣ Dra. Cinthia Ruiz\n4️⃣ Dra. Gisela Cuevas\n5️⃣ Dra. Gabriela Sánchez"
    }
}

HORARIOS_PRIMERA_VEZ = {
    "type": "text",
    "text": {
        "body": "Lunes: 9:00 – 19:00 hrs (comida 13:00–14:00)\nMartes: 9:00–11:00 hrs\nMiércoles: 15:00–20:00 hrs\nJueves: 9:00–12:00 / 15:00–18:00 hrs\nViernes: 9:00–15:00 hrs\nSábado: 10:00–11:30 hrs (solo fertilidad y SOP)"
    }
}

HORARIOS_SUBSECUENTE = {
    "type": "text",
    "text": {
        "body": "Lunes: 9:00 – 19:00 hrs (comida 13:00–14:00)\nMartes: 9:00–11:00 hrs\nMiércoles: 15:00–20:00 hrs\nJueves: 9:00–12:00 / 15:00–18:00 hrs\nViernes: 9:00–15:00 hrs\nSábado: 8:00–15:00 hrs (solo fertilidad y SOP)"
    }
}

COSTOS = {
    "type": "text",
    "text": {
        "body": "💰 Nuestros costos:\n\n• PAQUETE CHECK UP: $1,800 pesos\n• CONSULTA DE FERTILIDAD: $1,500 pesos\n• CONSULTA PRENATAL: $1,500 pesos\n• ESPERMABIOTOSCOPIA: $1,500 pesos\n• ESPERMABIOTOSCOPIA CON FRAGMENTACIÓN: $4,500 pesos"
    }
}

CONFIRMACION = {
    "type": "text",
    "text": {
        "body": "✅ ¡Gracias por agendar tu cita con Milkiin!\n\n📍 Te esperamos en: Insurgentes Sur 1160, 6º piso, Colonia Del Valle. \n🗺️ [Ubicación en Google Maps](https://maps.app.goo.gl/VfWbVgwHLQrZPNrNA)\n\n💳 Aceptamos pagos con tarjeta (incluyendo AMEX) y en efectivo.\n\n⏰ Cancelación: avisa con 72 hrs de anticipación para reembolso.\n\nEstamos para acompañarte con profesionalismo y cariño ❤️. Si tienes dudas, escríbenos."
    }
}

# MAPEOS
ESPECIALISTAS_NOMBRES = {
    "1": "Dra. Mónica Olavarría",
    "2": "Dra. Graciela Guadarrama",
    "3": "Dra. Cinthia Ruiz",
    "4": "Dra. Gisela Cuevas",
    "5": "Dra. Gabriela Sánchez"
}

SERVICIOS_NOMBRES = {
    "1": "Fertilidad",
    "2": "Síndrome de Ovario Poliquístico",
    "3": "Chequeo Anual",
    "4": "Embarazo",
    "5": "Otros"
}

SERVICIOS_SUB_NOMBRES = {
    "1": "Fertilidad",
    "2": "Síndrome de Ovario Poliquístico",
    "3": "Chequeo Anual",
    "4": "Embarazo",
    "5": "Revisión de estudios",
    "6": "Seguimiento folicular",
    "7": "Otros"
}

DURACIONES_PRIMERA_VEZ = {"1": 90, "2": 60, "3": 60, "4": 60, "5": 30}
DURACIONES_SUBSECUENTE = {"1": 45, "2": 45, "3": 45, "4": 45, "5": 30, "6": 30, "7": 30}

# === FUNCIONES PARA WHATSAPP META API ===
def send_whatsapp_message(phone_number, message_data):
    try:
        url = f"https://graph.facebook.com/v22.0/{META_PHONE_NUMBER_ID}/messages"
        headers = {
            'Authorization': f'Bearer {META_ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        }
        formatted_phone = format_phone_number(phone_number)
        payload = {
            "messaging_product": "whatsapp",
            "to": formatted_phone,
            "type": message_data["type"]
        }
        if message_data["type"] == "text":
            payload["text"] = message_data["text"]
        elif message_data["type"] == "template":
            payload["template"] = message_data["template"]

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            print(f"✅ Mensaje enviado a {phone_number}")
            return response.json()
        else:
            print(f"❌ Error API WhatsApp: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error en send_whatsapp_message: {e}")
        return None

def format_phone_number(phone):
    clean_phone = re.sub(r'\D', '', phone)
    if clean_phone.startswith('52') and len(clean_phone) == 12:
        return clean_phone
    elif clean_phone.startswith('1') and len(clean_phone) == 11:
        return '52' + clean_phone[1:]
    elif len(clean_phone) == 10:
        return '52' + clean_phone
    return clean_phone

def extract_user_data(message_body):
    data = {}
    lines = message_body.split('\n')
    for line in lines:
        if 'nombre' in line.lower() or 'paciente' in line.lower():
            data['nombre'] = line.split(':', 1)[1].strip() if ':' in line else line.strip()
        elif re.search(r'\d{10,}', line):
            phone_match = re.search(r'\d{10,}', line)
            if phone_match:
                data['telefono'] = phone_match.group(0)
    return data

# === FUNCIONES PARA GOOGLE CALENDAR ===
def crear_evento_google_calendar(resumen, inicio, duracion_minutos, descripcion):
    try:
        service = get_calendar_service()
        if not service:
            print("❌ Servicio de Google Calendar no disponible.")
            return None

        fin = inicio + timedelta(minutes=duracion_minutos)
        event = {
            'summary': resumen,
            'description': descripcion,
            'start': {'dateTime': inicio.isoformat(), 'timeZone': 'America/Mexico_City'},
            'end': {'dateTime': fin.isoformat(), 'timeZone': 'America/Mexico_City'},
            'attendees': [{'email': GOOGLE_CALENDAR_ID}],
        }
        event = service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event).execute()
        print(f"✅ Evento creado: {event.get('htmlLink')}")
        return event.get('htmlLink')
    except HttpError as error:
        print(f"❌ HttpError al crear evento: {error}")
        return None
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return None

# === FUNCIONES DE CORREO ELECTRÓNICO ===
def send_appointment_email(recipient_email, patient_name, doctor_name, appointment_date, appointment_time):
    if not all([EMAIL_ADDRESS, EMAIL_PASSWORD, recipient_email]):
        print("❌ Credenciales de correo incompletas.")
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = "Confirmación de Cita - Milkiin"
    message["From"] = EMAIL_ADDRESS
    message["To"] = recipient_email

    text = f"Hola {patient_name},\n\nTu cita con la Dra. {doctor_name} ha sido agendada.\nFecha: {appointment_date}\nHora: {appointment_time}\n\nSaludos,\nEquipo Milkiin"
    html = f"""
    <html><body>
      <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;border:1px solid #ddd;border-radius:10px;">
        <h2 style="color:#4CAF50;">✅ Cita Confirmada</h2>
        <p>Hola <strong>{patient_name}</strong>,</p>
        <p>Tu cita con la <strong>Dra. {doctor_name}</strong> ha sido agendada.</p>
        <ul><li><strong>Fecha:</strong> {appointment_date}</li><li><strong>Hora:</strong> {appointment_time}</li></ul>
        <p>¡Esperamos verte pronto!</p>
        <p>El equipo de Milkiin</p>
      </div>
    </body></html>
    """
    message.attach(MIMEText(text, "plain"))
    message.attach(MIMEText(html, "html"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, recipient_email, message.as_string())
            print(f"✅ Correo enviado a {recipient_email}")
            return True
    except Exception as e:
        print(f"❌ Error al enviar correo: {e}")
        return False

# === PROCESAMIENTO DE MENSAJES ===
def process_user_message(phone_number, message_body):
    user_data = user_state.get(phone_number, {"stage": "start"})
    user_info = user_data_storage.get(phone_number, {})
    print(f"[MENSAJE] {phone_number}: {message_body} | Etapa: {user_data['stage']}")

    # --- Inicio ---
    if user_data["stage"] == "start":
        send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        user_data["stage"] = "option_selected"

    # --- Opciones principales ---
    elif user_data["stage"] == "option_selected":
        if message_body == "1":
            user_data.update({"tipo": "primera_vez", "stage": "servicio_primera"})
            send_whatsapp_message(phone_number, SERVICIOS_PRIMERA_VEZ)
        elif message_body == "2":
            user_data.update({"tipo": "subsecuente", "stage": "servicio_subsecuente"})
            send_whatsapp_message(phone_number, SERVICIOS_SUBSECUENTE)
        elif message_body == "3":
            user_data["stage"] = "atencion_cliente"
            send_whatsapp_message(phone_number, {"type": "text", "text": {"body": "1️⃣ COSTOS\n2️⃣ Hablar con América"}})
        elif message_body == "4":
            user_data["stage"] = "facturacion"
            send_whatsapp_message(phone_number, {"type": "text", "text": {"body": "1️⃣ Requiero factura\n2️⃣ Dudas"}})
        elif message_body == "5":
            send_whatsapp_message(phone_number, {"type": "text", "text": {"body": "📧 gine.moni.og@gmail.com"}})
            send_whatsapp_message(phone_number, WELCOME_MESSAGE)
            user_data["stage"] = "option_selected"
        elif message_body == "6":
            send_whatsapp_message(phone_number, {"type": "text", "text": {"body": "Escribe tu duda brevemente."}})
            user_data["stage"] = "dudas"
        else:
            send_whatsapp_message(phone_number, {"type": "text", "text": {"body": "Por favor, elige una opción del 1 al 6."}})

    # --- Primera vez ---
    elif user_data["stage"] == "servicio_primera":
        if message_body in ["1", "2", "3", "4"]:
            user_data["servicio"] = message_body
            user_data["stage"] = "especialista"
            send_whatsapp_message(phone_number, ESPECIALISTAS)
        elif message_body == "5":
            user_data["servicio"] = "5"
            user_data["stage"] = "otros_opciones"
            send_whatsapp_message(phone_number, OTROS_OPCIONES)
        else:
            send_whatsapp_message(phone_number, {"type": "text", "text": {"body": "Elige 1-5."}})

    elif user_data["stage"] == "otros_opciones":
        if message_body == "3":
            send_whatsapp_message(phone_number, {"type": "text", "text": {"body": "Conectando con América..."}})
        send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        user_data["stage"] = "option_selected"

    elif user_data["stage"] == "especialista":
        if message_body in ["1", "2", "3", "4", "5"]:
            user_data["especialista"] = message_body
            user_data["stage"] = "pedir_datos_sin_correo"
            send_whatsapp_message(phone_number, {"type": "text", "text": {"body": "Nombre completo\nTeléfono\nFecha de nacimiento\nEdad"}})
        else:
            send_whatsapp_message(phone_number, {"type": "text", "text": {"body": "Elige 1-5."}})

    elif user_data["stage"] == "pedir_datos_sin_correo":
        user_info.update(extract_user_data(message_body))
        user_data_storage[phone_number] = user_info
        user_data["stage"] = "esperando_correo"
        send_whatsapp_message(phone_number, {"type": "text", "text": {"body": "Gracias. Ahora envíanos tu correo electrónico."}})

    elif user_data["stage"] == "esperando_correo":
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message_body)
        if email_match:
            user_info["correo"] = email_match.group(0)
            user_data_storage[phone_number] = user_info
            user_data["stage"] = "mostrar_horarios"
            send_whatsapp_message(phone_number, HORARIOS_PRIMERA_VEZ)
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "📌 Anticipo de $500 MXN. Datos: Banco BBVA, Cuenta: 048 482 8712, CLABE: 012180004848287122"}
            })
            send_whatsapp_message(phone_number, {"type": "text", "text": {"body": "Envía fecha y hora (ej: 2025-04-05 10:00)"}})
            user_data["stage"] = "esperando_fecha"
        else:
            send_whatsapp_message(phone_number, {"type": "text", "text": {"body": "Correo inválido. Inténtalo de nuevo."}})

    # --- Subsecuente ---
    elif user_data["stage"] == "servicio_subsecuente":
        if message_body in map(str, range(1, 8)):
            user_data["servicio"] = message_body
            user_data["stage"] = "datos_subsecuente"
            send_whatsapp_message(phone_number, {"type": "text", "text": {"body": "Nombre\nCorreo\nTeléfono\nFecha de nacimiento\nEdad"}})
        elif message_body == "7":
            user_data["stage"] = "otros_opciones_sub"
            send_whatsapp_message(phone_number, OTROS_OPCIONES)
        else:
            send_whatsapp_message(phone_number, {"type": "text", "text": {"body": "Elige 1-7."}})

    elif user_data["stage"] == "datos_subsecuente":
        user_info.update(extract_user_data(message_body))
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message_body)
        if email_match:
            user_info["correo"] = email_match.group(0)
        user_data_storage[phone_number] = user_info
        user_data["stage"] = "mostrar_horarios_sub"
        send_whatsapp_message(phone_number, HORARIOS_SUBSECUENTE)
        send_whatsapp_message(phone_number, {"type": "text", "text": {"body": "Envía fecha y hora (ej: 2025-04-05 10:00)"}})
        user_data["stage"] = "esperando_fecha_sub"

    # --- Agendar cita (Primera vez) ---
    elif user_data["stage"] == "esperando_fecha":
        try:
            fecha_hora_naive = datetime.strptime(message_body.strip(), "%Y-%m-%d %H:%M")
            fecha_hora = mexico_tz.localize(fecha_hora_naive)

            servicio_key = user_data.get("servicio", "1")
            duracion = DURACIONES_PRIMERA_VEZ.get(servicio_key, 60)
            servicio_nombre = SERVICIOS_NOMBRES.get(servicio_key, "Consulta")
            especialista_key = user_data.get("especialista", "1")
            especialista_nombre = ESPECIALISTAS_NOMBRES.get(especialista_key, "No definido")
            nombre_paciente = user_info.get('nombre', 'Paciente')

            descripcion = f"Paciente: {nombre_paciente}\nTeléfono: {phone_number}\nServicio: {servicio_nombre}\nEspecialista: {especialista_nombre}"
            link = crear_evento_google_calendar(
                resumen=f"Cita - {servicio_nombre} con {especialista_nombre}",
                inicio=fecha_hora,
                duracion_minutos=duracion,
                descripcion=descripcion
            )

            if not link:
                send_whatsapp_message(phone_number, {
                    "type": "text",
                    "text": {"body": "⚠️ No se pudo agendar. Intenta más tarde o contáctanos."}
                })
                return

            if user_info.get('correo'):
                send_appointment_email(
                    user_info['correo'],
                    nombre_paciente,
                    especialista_nombre,
                    fecha_hora.strftime("%Y-%m-%d"),
                    fecha_hora.strftime("%H:%M")
                )

            send_whatsapp_message(phone_number, CONFIRMACION)
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": f"📅 Cita agendada:\n{servicio_nombre}\n{especialista_nombre}\n{fecha_hora.strftime('%Y-%m-%d %H:%M')}"}
            })

            del user_state[phone_number], user_data_storage[phone_number]

        except ValueError:
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Formato: AAAA-MM-DD HH:MM (ej: 2025-04-05 10:00)"}
            })

    # --- Agendar cita (Subsecuente) ---
    elif user_data["stage"] == "esperando_fecha_sub":
        try:
            fecha_hora_naive = datetime.strptime(message_body.strip(), "%Y-%m-%d %H:%M")
            fecha_hora = mexico_tz.localize(fecha_hora_naive)

            servicio_key = user_data.get("servicio", "1")
            duracion = DURACIONES_SUBSECUENTE.get(servicio_key, 45)
            servicio_nombre = SERVICIOS_SUB_NOMBRES.get(servicio_key, "Consulta")
            nombre_paciente = user_info.get('nombre', 'Paciente')

            link = crear_evento_google_calendar(
                resumen=f"Cita - {servicio_nombre} (Subsecuente)",
                inicio=fecha_hora,
                duracion_minutos=duracion,
                descripcion=f"Paciente: {nombre_paciente}\nTeléfono: {phone_number}\nServicio: {servicio_nombre}"
            )

            if not link:
                send_whatsapp_message(phone_number, {
                    "type": "text",
                    "text": {"body": "⚠️ Error al agendar. Intenta más tarde."}
                })
                return

            if user_info.get('correo'):
                send_appointment_email(
                    user_info['correo'],
                    nombre_paciente,
                    "No especificado",
                    fecha_hora.strftime("%Y-%m-%d"),
                    fecha_hora.strftime("%H:%M")
                )

            send_whatsapp_message(phone_number, CONFIRMACION)
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": f"📅 Cita agendada:\n{servicio_nombre}\n{fecha_hora.strftime('%Y-%m-%d %H:%M')}"}
            })

            del user_state[phone_number], user_data_storage[phone_number]

        except ValueError:
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Formato: AAAA-MM-DD HH:MM"}
            })

    