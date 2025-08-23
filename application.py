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

# Importaciones para Google Calendar API
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Importaciones para iCalendar (.ics)
from icalendar import Calendar, Event as IcsEvent
import tempfile
import os

# Crear la aplicación Flask (cambiar 'app' por 'application' para Passenger)
application = Flask(__name__)

# === CONFIGURACIÓN ===
META_ACCESS_TOKEN = os.environ.get('META_ACCESS_TOKEN') or 'temporal_token_placeholder'
META_PHONE_NUMBER_ID = os.environ.get('META_PHONE_NUMBER_ID') or '123456789012345'
META_VERIFY_TOKEN = os.environ.get('META_VERIFY_TOKEN') or 'milkiin_verify_token_2024'

# Variables para Google Calendar
GOOGLE_CALENDAR_CREDENTIALS_JSON = os.environ.get('GOOGLE_CALENDAR_CREDENTIALS')
GOOGLE_CALENDAR_ID = os.environ.get('GOOGLE_CALENDAR_ID')
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

# === CONFIGURACIÓN DE CORREO ELECTRÓNICO ===
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 465

# === AUTENTICACIÓN Y SERVICIO DE CALENDAR ===
def get_calendar_service():
    try:
        info = json.loads(GOOGLE_CALENDAR_CREDENTIALS_JSON)
        credentials = service_account.Credentials.from_service_account_info(
            info,
            scopes=SCOPES
        )
        service = build('calendar', 'v3', credentials=credentials)
        return service
    except (json.JSONDecodeError, HttpError) as e:
        print(f"❌ Error al inicializar el servicio de Google Calendar: {e}")
        return None

# === ESTADO DE CONVERSACIÓN ===
user_state = {}
user_data_storage = {}

# === MENSAJES DEL BOT ===
WELCOME_MESSAGE = {
    "type": "text",
    "text": {
        "body": "👋 ¡Hola! Bienvenido(a) a Milkiin, donde cada paso en tu camino a la maternidad cuenta. ✨ Soy MilkiBot, tu asistente virtual, y estoy aquí para ayudarte con todo lo que necesites.\n\n¿En qué te puedo apoyar hoy?\n\n1️⃣ Paciente de primera vez\n2️⃣ Paciente subsecuente\n3️⃣ Atención al cliente\n4️⃣ Facturación\n5️⃣ Envío de Resultados\n6️⃣ Dudas"
    }
}

SERVICIOS_PRIMERA_VEZ = {
    "type": "text",
    "text": {
        "body": "Selecciona el servicio de primera vez:\n1️⃣ Fertilidad\n2️⃣ Síndrome de Ovario Poliquístico\n3️⃣ Chequeo Anual\n4️⃣ Embarazo\n5️⃣ Ginecología Pediátrica y Adolescentes\n6️⃣ Revisión de Estudios\n7️⃣ Otros"
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

# === MAPEOS Y LÓGICA DE ESPECIALISTAS ===
ESPECIALISTAS_NOMBRES = {
    "1": "Dra. Mónica Olavarría",
    "2": "Dra. Graciela Guadarrama",
    "3": "Dra. Cinthia Ruiz",
    "4": "Dra. Gisela Cuevas",
    "5": "Dra. Gabriela Sánchez"
}

ESPECIALISTAS_POR_SERVICIO = {
    "1": ["1", "4"],  # Fertilidad: Mónica, Gisela
    "2": ["1", "3", "4"],  # SOP: Mónica, Cinthia, Gisela
    "3": ["1", "2", "3", "4", "5"],  # Chequeo Anual: Todas
    "4": ["1", "2", "3", "4", "5"],  # Embarazo: Todas
    "5": ["3"],  # Ginecología Pediátrica: Cinthia
    "6": ["1", "2", "3", "4", "5"],  # Revisión de Estudios: Todas
}

def get_specialist_menu(service_key):
    especialistas_disponibles = ESPECIALISTAS_POR_SERVICIO.get(service_key, [])
    if not especialistas_disponibles:
        return None
    menu_text = "Selecciona tu especialista:\n"
    for key in especialistas_disponibles:
        menu_text += f"▪️ {key}: {ESPECIALISTAS_NOMBRES[key]}\n"
    return {
        "type": "text",
        "text": {"body": menu_text}
    }

SERVICIOS_NOMBRES = {
    "1": "Fertilidad",
    "2": "Síndrome de Ovario Poliquístico",
    "3": "Chequeo Anual",
    "4": "Embarazo",
    "5": "Ginecología Pediátrica y Adolescentes",
    "6": "Revisión de Estudios",
    "7": "Otros"
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

DURACIONES_PRIMERA_VEZ = {
    "1": 90,
    "2": 60,
    "3": 60,
    "4": 60,
    "5": 60,
    "6": 30,
    "7": 30
}

DURACIONES_SUBSECUENTE = {
    "1": 45,
    "2": 45,
    "3": 45,
    "4": 45,
    "5": 30,
    "6": 30,
    "7": 30
}

COSTOS = {
    "type": "text",
    "text": {
        "body": "💰 Nuestros costos:\n\n• PAQUETE CHECK UP: $1,800 pesos (incluye papanicolaou, USG , revisión de mamas, colposcopia y consulta)\n• CONSULTA DE FERTILIDAD: $1,500 pesos. (incluye ultrasonido)\n• CONSULTA PRENATAL: $1,500 pesos. (incluye ultrasonido)\n• ESPERMABIOTOSCOPIA: $1,500 pesos\n• ESPERMABIOTOSCOPIA CON FRAGMENTACIÓN: $4,500 pesos"
    }
}

CONFIRMACION = {
    "type": "text",
    "text": {
        "body": "✅ ¡Gracias por agendar tu cita con Milkiin!\n\n📍 Te esperamos en: Insurgentes Sur 1160, 6º piso, Colonia Del Valle. \n🗺️ [Ubicación en Google Maps](https://maps.app.goo.gl/VfWbVgwHLQrZPNrNA)\n\n💳 Aceptamos pagos con tarjeta (incluyendo AMEX) y en efectivo.\n\n⏰ En caso de cancelación, es necesario avisar con mínimo 72 horas de anticipación para poder realizar el reembolso del anticipo y reprogramar tu cita. Si no se cumple con este plazo, lamentablemente no podremos hacer el reembolso.\n\nAgradecemos tu comprensión y tu confianza. Estamos para acompañarte con profesionalismo y cariño en cada paso ❤️. Si tienes alguna duda o necesitas apoyo adicional, no dudes en escribirnos."
    }
}

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
            print(f"❌ Error enviando mensaje: {response.status_code} - {response.text}")
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
            data['nombre'] = line.split(':', 1)[1].strip() if ':' in line else line
        elif re.search(r'\d{10,}', line):
            phone_match = re.search(r'\d{10,}', line)
            if phone_match:
                data['telefono'] = phone_match.group(0)
    return data

# === GENERAR ARCHIVO .ICS ===
def generar_archivo_ics(nombre_paciente, servicio, especialista, fecha_hora, duracion_minutos):
    cal = Calendar()
    event = IcsEvent()
    event.add('summary', f"Cita en Milkiin - {servicio}")
    event.add('dtstart', fecha_hora)
    event.add('dtend', fecha_hora + timedelta(minutes=duracion_minutos))
    event.add('location', "Insurgentes Sur 1160, 6º piso, Colonia Del Valle, Ciudad de México")
    event.add('description', f"""
Cita agendada con éxito en Milkiin ❤️

Servicio: {servicio}
Especialista: {especialista}
Paciente: {nombre_paciente}

📍 Dirección: Insurgentes Sur 1160, 6º piso, Colonia Del Valle
🗺️ [Google Maps](https://maps.app.goo.gl/VfWbVgwHLQrZPNrNA)

💳 Aceptamos tarjeta (incluyendo AMEX) y efectivo.
⏰ Recordatorio: Si necesitas cancelar, avísanos con 72 horas de anticipación.

¡Te esperamos con cariño!
    """.strip())
    cal.add_component(event)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".ics")
    temp_file.write(cal.to_ical())
    temp_file.close()
    return temp_file.name

# === ENVIAR .ICS POR WHATSAPP ===
def send_whatsapp_document(phone_number, file_path, caption="📅 Tu cita ha sido agendada. Adjunto está el archivo para agregarla a tu calendario."):
    try:
        formatted_phone = format_phone_number(phone_number)
        media_upload_url = f"https://graph.facebook.com/v22.0/{META_PHONE_NUMBER_ID}/media"
        headers = {'Authorization': f'Bearer {META_ACCESS_TOKEN}'}
        with open(file_path, 'rb') as f:
            files = {
                'file': (os.path.basename(file_path), f, 'text/calendar')
            }
            data = {
                'messaging_product': 'whatsapp',
                'type': 'document'
            }
            response_upload = requests.post(media_upload_url, headers=headers, files=files, data=data)
        if response_upload.status_code != 200:
            print(f"❌ Error al subir archivo .ics: {response_upload.text}")
            return False
        media_id = response_upload.json().get('id')
        if not media_id:
            print("❌ No se recibió media_id después de subir el archivo.")
            return False
        send_url = f"https://graph.facebook.com/v22.0/{META_PHONE_NUMBER_ID}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": formatted_phone,
            "type": "document",
            "document": {
                "id": media_id,
                "filename": "cita_milkiin.ics",
                "caption": caption
            }
        }
        send_response = requests.post(send_url, headers=headers, json=payload)
        if send_response.status_code == 200:
            print("✅ Archivo .ics enviado por WhatsApp.")
            return True
        else:
            print(f"❌ Error al enviar documento por WhatsApp: {send_response.text}")
            return False
    except Exception as e:
        print(f"❌ Error en send_whatsapp_document: {e}")
        return False

# === GOOGLE CALENDAR ===
def crear_evento_google_calendar(resumen, inicio, duracion_minutos, descripcion):
    try:
        service = get_calendar_service()
        if not service:
            return None
        fin = inicio + timedelta(minutes=duracion_minutos)
        event = {
            'summary': resumen,
            'description': descripcion,
            'start': {
                'dateTime': inicio.isoformat(),
                'timeZone': 'America/Mexico_City',
            },
            'end': {
                'dateTime': fin.isoformat(),
                'timeZone': 'America/Mexico_City',
            },
        }
        event = service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event).execute()
        print(f"✅ Evento de Google Calendar creado: {event.get('htmlLink')}")
        return event.get('htmlLink')
    except HttpError as error:
        print(f"❌ Error al crear evento de Google Calendar: {error}")
        return None
    except Exception as e:
        print(f"❌ Error desconocido: {e}")
        return None

# === ENVÍO DE CORREO ===
def send_appointment_email(recipient_email, patient_name, doctor_name, appointment_date, appointment_time):
    if not all([EMAIL_ADDRESS, EMAIL_PASSWORD, recipient_email]):
        print("❌ Error: Faltan credenciales de correo o correo del destinatario.")
        return False
    message = MIMEMultipart("alternative")
    message["Subject"] = "Confirmación de Cita - Milkiin"
    message["From"] = EMAIL_ADDRESS
    message["To"] = recipient_email
    text = f"""
    Hola {patient_name},

    Tu cita con la Dra. {doctor_name} ha sido agendada con éxito.

    Detalles de la cita:
    Fecha: {appointment_date}
    Hora: {appointment_time}

    Te esperamos en nuestras instalaciones. Si tienes alguna duda, responde a este correo.

    Saludos cordiales,
    El equipo de Milkiin
    """
    html = f"""
    <html>
      <body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
          <h2 style="color: #4CAF50;">✅ Cita Confirmada</h2>
          <p>Hola <strong>{patient_name}</strong>,</p>
          <p>Tu cita con la <strong>Dra. {doctor_name}</strong> ha sido agendada con éxito.</p>
          <p>Aquí están los detalles de tu cita:</p>
          <ul>
            <li><strong>Fecha:</strong> {appointment_date}</li>
            <li><strong>Hora:</strong> {appointment_time}</li>
          </ul>
          <p>¡Esperamos verte pronto!</p>
          <p>Si necesitas reagendar o tienes alguna pregunta, por favor contáctanos.</p>
          <p style="margin-top: 30px;">
            Saludos cordiales,<br>
            El equipo de Milkiin
          </p>
          <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
          <p style="font-size: 12px; color: #999;">Este es un mensaje automático, por favor no lo respondas directamente si no es para dudas sobre tu cita.</p>
        </div>
      </body>
    </html>
    """
    part1 = MIMEText(text, "plain")
    part2 = MIMEText(html, "html")
    message.attach(part1)
    message.attach(part2)
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
    print(f"[MENSAJE ENTRANTE] {phone_number}: {message_body}")

    if message_body.lower() == "hola" and user_data["stage"] != "start":
        user_data["stage"] = "start"
        send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        user_state[phone_number] = user_data
        return
    
    if user_data["stage"] == "start":
        send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        user_data["stage"] = "option_selected"

    elif user_data["stage"] == "option_selected":
        if message_body == "1":
            user_data["tipo"] = "primera_vez"
            user_data["stage"] = "servicio_primera"
            send_whatsapp_message(phone_number, SERVICIOS_PRIMERA_VEZ)
        elif message_body == "2":
            user_data["tipo"] = "subsecuente"
            user_data["stage"] = "servicio_subsecuente"
            send_whatsapp_message(phone_number, SERVICIOS_SUBSECUENTE)
        elif message_body == "3":
            user_data["stage"] = "atencion_cliente"
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "1️⃣ COSTOS\n2️⃣ Hablar con América"}
            })
        elif message_body == "4":
            user_data["stage"] = "facturacion"
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "1️⃣ Requiero factura\n2️⃣ Dudas"}
            })
        elif message_body == "5":
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Para el envío de resultados, envíalos al correo:\n📧 nicontacto@heyginemoni.com"}
            })
            # Reinicia la conversación después de dar la información
            user_data["stage"] = "start"
            send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        elif message_body == "6":
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Para dudas o cancelaciones, puedes escribirnos a:\n📧 contacto@heyginemoni.com"}
            })
            user_data["stage"] = "start"
            send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        else:
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, selecciona una opción válida del 1 al 6."}
            })

    # === PRIMERA VEZ ===
    elif user_data["stage"] == "servicio_primera":
        if message_body in ["1", "2", "3", "4", "5", "6"]:
            user_data["servicio"] = message_body
            user_data["stage"] = "especialista"
            especialista_menu = get_specialist_menu(message_body)
            if especialista_menu:
                send_whatsapp_message(phone_number, especialista_menu)
            else:
                send_whatsapp_message(phone_number, {
                    "type": "text",
                    "text": {"body": "No hay especialistas disponibles para este servicio."}
                })
                user_data["stage"] = "start"
                send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        elif message_body == "7":
            user_data["servicio"] = "7"
            user_data["stage"] = "otros_opciones"
            send_whatsapp_message(phone_number, OTROS_OPCIONES)
        else:
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, elige una opción válida (1-7)."}
            })

    elif user_data["stage"] == "otros_opciones":
        if message_body == "3":
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Conectando con América... Un miembro del equipo te contactará pronto."}
            })
            user_data["stage"] = "start"
            send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        else:
            user_data["servicio"] = message_body
            user_data["stage"] = "esperando_nombre"
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, envía tu nombre completo."}
            })

    elif user_data["stage"] == "especialista":
        valid_specialists = ESPECIALISTAS_POR_SERVICIO.get(user_data["servicio"], [])
        if message_body in valid_specialists:
            user_data["especialista"] = message_body
            user_data["stage"] = "esperando_nombre"
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, envía tu nombre completo."}
            })
        else:
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, elige una opción válida de la lista."}
            })
    
    # --- Nuevos estados para pedir datos individualmente (Primera vez) ---
    elif user_data["stage"] == "esperando_nombre":
        user_info["nombre"] = message_body.strip()
        user_data_storage[phone_number] = user_info
        user_data["stage"] = "esperando_telefono"
        send_whatsapp_message(phone_number, {
            "type": "text",
            "text": {"body": "Gracias. Ahora, por favor, envía tu número de teléfono."}
        })

    elif user_data["stage"] == "esperando_telefono":
        user_info["telefono"] = message_body.strip()
        user_data_storage[phone_number] = user_info
        user_data["stage"] = "esperando_fecha_nacimiento"
        send_whatsapp_message(phone_number, {
            "type": "text",
            "text": {"body": "Por favor, envía tu fecha de nacimiento (DD-MM-AAAA)."}
        })

    elif user_data["stage"] == "esperando_fecha_nacimiento":
        user_info["fecha_nacimiento"] = message_body.strip()
        user_data_storage[phone_number] = user_info
        user_data["stage"] = "esperando_edad"
        send_whatsapp_message(phone_number, {
            "type": "text",
            "text": {"body": "Por último, ¿cuántos años tienes?"}
        })
    
    elif user_data["stage"] == "esperando_edad":
        user_info["edad"] = message_body.strip()
        user_data_storage[phone_number] = user_info
        user_data["stage"] = "esperando_correo"
        send_whatsapp_message(phone_number, {
            "type": "text",
            "text": {"body": "Gracias. Ahora, por favor, envíanos tu correo electrónico para enviarte la confirmación."}
        })
    # --- Fin de nuevos estados ---

    elif user_data["stage"] == "esperando_correo":
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message_body)
        if email_match:
            user_info["correo"] = email_match.group(0)
            user_data_storage[phone_number] = user_info
            user_data["stage"] = "mostrar_horarios"
            send_whatsapp_message(phone_number, HORARIOS_PRIMERA_VEZ)
            pago_info = {
                "type": "text",
                "text": {
                    "body": "Te compartimos una información importante: 📌 Para consultas de primera vez, solicitamos un anticipo de $500 MXN. El monto restante se cubrirá el día de tu consulta, una vez finalizada. Esta medida nos permite asegurar tu lugar, ya que contamos con alta demanda.\n\nFavor de enviar su comprobante de pago al correo: milkiin.gine@gmail.com\n\nDatos para pago:\nBanco: BBVA\nCuenta: 048 482 8712\nCLABE: 012180004848287122"
                }
            }
            send_whatsapp_message(phone_number, pago_info)
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, envía la fecha y hora que prefieras (ej: 2025-04-05 10:00)"}
            })
            user_data["stage"] = "esperando_fecha"
        else:
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "El formato del correo es incorrecto. Por favor, inténtalo de nuevo."}
            })

    # === SUBSECUENTE ===
    elif user_data["stage"] == "servicio_subsecuente":
        if message_body in ["1", "2", "3", "4", "5", "6"]:
            user_data["servicio"] = message_body
            user_data["stage"] = "esperando_nombre_sub"
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, envía tu nombre completo."}
            })
        elif message_body == "7":
            user_data["servicio"] = "7"
            user_data["stage"] = "otros_opciones_sub"
            send_whatsapp_message(phone_number, OTROS_OPCIONES)
        else:
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, elige una opción válida (1-7)."}
            })

    elif user_data["stage"] == "otros_opciones_sub":
        if message_body == "3":
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Conectando con América... Un miembro del equipo te contactará pronto."}
            })
            user_data["stage"] = "start"
            send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        else:
            user_data["servicio"] = message_body
            user_data["stage"] = "esperando_nombre_sub"
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, envía tu nombre completo."}
            })

    # --- Nuevos estados para pedir datos individualmente (Subsecuente) ---
    elif user_data["stage"] == "esperando_nombre_sub":
        user_info["nombre"] = message_body.strip()
        user_data_storage[phone_number] = user_info
        user_data["stage"] = "esperando_telefono_sub"
        send_whatsapp_message(phone_number, {
            "type": "text",
            "text": {"body": "Gracias. Ahora, por favor, envía tu número de teléfono."}
        })
    
    elif user_data["stage"] == "esperando_telefono_sub":
        user_info["telefono"] = message_body.strip()
        user_data_storage[phone_number] = user_info
        user_data["stage"] = "esperando_fecha_nacimiento_sub"
        send_whatsapp_message(phone_number, {
            "type": "text",
            "text": {"body": "Por favor, envía tu fecha de nacimiento (DD-MM-AAAA)."}
        })

    elif user_data["stage"] == "esperando_fecha_nacimiento_sub":
        user_info["fecha_nacimiento"] = message_body.strip()
        user_data_storage[phone_number] = user_info
        user_data["stage"] = "esperando_edad_sub"
        send_whatsapp_message(phone_number, {
            "type": "text",
            "text": {"body": "Por último, ¿cuántos años tienes?"}
        })

    elif user_data["stage"] == "esperando_edad_sub":
        user_info["edad"] = message_body.strip()
        user_data_storage[phone_number] = user_info
        user_data["stage"] = "esperando_correo_sub"
        send_whatsapp_message(phone_number, {
            "type": "text",
            "text": {"body": "Gracias. Ahora, por favor, envíanos tu correo electrónico para enviarte la confirmación."}
        })

    elif user_data["stage"] == "esperando_correo_sub":
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message_body)
        if email_match:
            user_info["correo"] = email_match.group(0)
            user_data_storage[phone_number] = user_info
            user_data["stage"] = "mostrar_horarios_sub"
            send_whatsapp_message(phone_number, HORARIOS_SUBSECUENTE)
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, responde con la fecha y hora que prefieras (ej: 2025-04-05 10:00)"}
            })
            user_data["stage"] = "esperando_fecha_sub"
        else:
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "El formato del correo es incorrecto. Por favor, inténtalo de nuevo."}
            })
    # --- Fin de nuevos estados (Subsecuente) ---
    
    # === AGENDAR CITA (PRIMERA VEZ) ===
    elif user_data["stage"] == "esperando_fecha":
        try:
            fecha_hora_str = message_body.strip()
            fecha_hora = datetime.strptime(fecha_hora_str, "%Y-%m-%d %H:%M")
            servicio_key = user_data.get("servicio", "1")
            duracion = DURACIONES_PRIMERA_VEZ.get(servicio_key, 60)
            servicio_nombre = SERVICIOS_NOMBRES.get(servicio_key, "Consulta")
            especialista_key = user_data.get("especialista", "1")
            especialista_nombre = ESPECIALISTAS_NOMBRES.get(especialista_key, "No definido")
            nombre_paciente = user_info.get('nombre', 'Paciente Anónimo')

            crear_evento_google_calendar(
                resumen=f"Cita - {servicio_nombre} con {especialista_nombre}",
                inicio=fecha_hora,
                duracion_minutos=duracion,
                descripcion=f"Paciente: {nombre_paciente}\nTeléfono: {phone_number}\nServicio: {servicio_nombre}\nEspecialista: {especialista_nombre}"
            )

            if user_info.get('correo'):
                send_appointment_email(
                    user_info['correo'],
                    nombre_paciente,
                    especialista_nombre,
                    fecha_hora.strftime("%Y-%m-%d"),
                    fecha_hora.strftime("%H:%M")
                )

            try:
                ics_path = generar_archivo_ics(
                    nombre_paciente=nombre_paciente,
                    servicio=servicio_nombre,
                    especialista=especialista_nombre,
                    fecha_hora=fecha_hora,
                    duracion_minutos=duracion
                )
                send_whatsapp_document(phone_number, ics_path)
                os.unlink(ics_path)
            except Exception as e:
                print(f"⚠️ No se pudo enviar .ics: {e}")

            send_whatsapp_message(phone_number, CONFIRMACION)
            cita_detalle = {
                "type": "text",
                "text": {
                    "body": f"📅 CONFIRMACIÓN DE CITA\n\nServicio: {servicio_nombre}\nEspecialista: {especialista_nombre}\nFecha y hora: {fecha_hora_str}\nDuración estimada: {duracion} minutos"
                }
            }
            send_whatsapp_message(phone_number, cita_detalle)
            
            # Limpiar el estado de conversación al finalizar el proceso
            del user_state[phone_number]
            del user_data_storage[phone_number]

        except ValueError:
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, envía la fecha y hora en formato: AAAA-MM-DD HH:MM\nEj: 2025-04-05 10:00"}
            })

    # === AGENDAR CITA (SUBSECUENTE) ===
    elif user_data["stage"] == "esperando_fecha_sub":
        try:
            fecha_hora_str = message_body.strip()
            fecha_hora = datetime.strptime(fecha_hora_str, "%Y-%m-%d %H:%M")
            servicio_key = user_data.get("servicio", "1")
            duracion = DURACIONES_SUBSECUENTE.get(servicio_key, 45)
            servicio_nombre = SERVICIOS_SUB_NOMBRES.get(servicio_key, "Consulta")
            nombre_paciente = user_info.get('nombre', 'Paciente Anónimo')
            especialista_nombre = "Por definir"

            crear_evento_google_calendar(
                resumen=f"Cita - {servicio_nombre} (Subsecuente)",
                inicio=fecha_hora,
                duracion_minutos=duracion,
                descripcion=f"Paciente: {nombre_paciente}\nTeléfono: {phone_number}\nServicio: {servicio_nombre}"
            )

            if user_info.get('correo'):
                send_appointment_email(
                    user_info['correo'],
                    nombre_paciente,
                    especialista_nombre,
                    fecha_hora.strftime("%Y-%m-%d"),
                    fecha_hora.strftime("%H:%M")
                )

            try:
                ics_path = generar_archivo_ics(
                    nombre_paciente=nombre_paciente,
                    servicio=servicio_nombre,
                    especialista=especialista_nombre,
                    fecha_hora=fecha_hora,
                    duracion_minutos=duracion
                )
                send_whatsapp_document(phone_number, ics_path)
                os.unlink(ics_path)
            except Exception as e:
                print(f"⚠️ No se pudo enviar .ics: {e}")

            send_whatsapp_message(phone_number, CONFIRMACION)
            cita_detalle = {
                "type": "text",
                "text": {
                    "body": f"📅 CONFIRMACIÓN DE CITA\n\nServicio: {servicio_nombre}\nFecha y hora: {fecha_hora_str}\nDuración estimada: {duracion} minutos"
                }
            }
            send_whatsapp_message(phone_number, cita_detalle)
            
            # Limpiar el estado de conversación al finalizar el proceso
            del user_state[phone_number]
            del user_data_storage[phone_number]

        except ValueError:
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, envía la fecha y hora en formato: AAAA-MM-DD HH:MM\nEj: 2025-04-05 10:00"}
            })

    # === ATENCIÓN AL CLIENTE ===
    elif user_data["stage"] == "atencion_cliente":
        if message_body == "1":
            send_whatsapp_message(phone_number, COSTOS)
        elif message_body == "2":
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Conectando con América... Un miembro del equipo te contactará pronto."}
            })
        user_data["stage"] = "start"
        send_whatsapp_message(phone_number, WELCOME_MESSAGE)

    # === FACTURACIÓN ===
    elif user_data["stage"] == "facturacion":
        if message_body == "1":
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, completa el formulario:\n🔗 [Formulario de facturación](https://docs.google.com/forms/d/e/1FAIpQLSfr1WWXWQGx4sZj3_0FnIp6XWBb1mol4GfVGfymflsRI0E5pA/viewform)"}
            })
        elif message_body == "2":
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Para dudas de facturación, escribe a:\n📧 lcastillo@gbcasesoria.mx"}
            })
        user_data["stage"] = "start"
        send_whatsapp_message(phone_number, WELCOME_MESSAGE)

    # === DUDAS ===
    elif user_data["stage"] == "dudas":
        send_whatsapp_message(phone_number, {
            "type": "text",
            "text": {"body": "Para dudas o cancelaciones, puedes escribirnos a:\n📧 contacto@heyginemoni.com"}
        })
        user_data["stage"] = "start"
        send_whatsapp_message(phone_number, WELCOME_MESSAGE)

    else:
        user_data["stage"] = "start"
        send_whatsapp_message(phone_number, WELCOME_MESSAGE)

    user_state[phone_number] = user_data

# === WEBHOOKS ===
@application.route('/webhook/', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode and token:
            if mode == 'subscribe' and token == META_VERIFY_TOKEN:
                return challenge
            else:
                return 'Verificación fallida', 403
    elif request.method == 'POST':
        try:
            data = request.get_json()
            if data.get('entry'):
                for entry in data['entry']:
                    if entry.get('changes'):
                        for change in entry['changes']:
                            if change.get('value') and change['value'].get('messages'):
                                messages = change['value']['messages']
                                for message in messages:
                                    phone_number = message['from']
                                    message_body = message.get('text', {}).get('body', '')
                                    process_user_message(phone_number, message_body)
            return 'EVENT_RECEIVED', 200
        except Exception as e:
            print(f"❌ Error en webhook: {e}")
            return 'Error', 500

@application.route('/')
def home():
    return jsonify({
        "message": "🤖 Bot de WhatsApp para Milkiin usando Meta API está activo",
        "status": "✅ Online",
        "version": "1.0.0"
    })

if __name__ == "__main__":
    application.run(debug=True)