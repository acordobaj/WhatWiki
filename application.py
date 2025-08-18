# application.py
from flask import Flask, request, jsonify
import requests
import json
import re
from datetime import datetime
import os
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Cambiado a 'application' para compatibilidad con Passenger
application = Flask(__name__)

# === CONFIGURACIÓN DE VARIABLES DE ENTORNO ===
# Usa variables de entorno (recomendado) o valores por defecto
META_ACCESS_TOKEN = os.environ.get('META_ACCESS_TOKEN')
META_PHONE_NUMBER_ID = os.environ.get('META_PHONE_NUMBER_ID')
META_VERIFY_TOKEN = os.environ.get('META_VERIFY_TOKEN')

# Valores por defecto (solo para desarrollo - ¡no usar en producción!)
if not META_ACCESS_TOKEN:
    logger.warning("⚠️ META_ACCESS_TOKEN no definido. Usando valor temporal.")
    META_ACCESS_TOKEN = "EAAB..."  # Reemplaza con tu token real

if not META_PHONE_NUMBER_ID:
    logger.warning("⚠️ META_PHONE_NUMBER_ID no definido.")
    META_PHONE_NUMBER_ID = "123456789012345"  # Reemplaza

if not META_VERIFY_TOKEN:
    logger.warning("⚠️ META_VERIFY_TOKEN no definido.")
    META_VERIFY_TOKEN = "milkiin_verify_token_2024"

# === ESTADO DE CONVERSACIÓN ===
user_state = {}
user_data_storage = {}

# === MENSAJES DEL BOT ===
WELCOME_MESSAGE = {
    "type": "text",
    "text": {
        "body": "👋 ¡Hola!\nBienvenido(a) a Milkiin,\ndonde cada paso en tu camino a la maternidad cuenta.\n✨\nSoy MilkiBot, tu asistente virtual, y estoy aquí\npara ayudarte con todo lo que necesites.\n¿En\nqué te puedo apoyar hoy?\n\n1️⃣ Paciente de primera vez\n2️⃣ Paciente subsecuente\n3️⃣ Atención al cliente\n4️⃣ Facturación\n5️⃣ Envío de Resultados\n6️⃣ Dudas\n\nPor favor, selecciona una opción para comenzar…"
    }
}

SERVICIOS_PRIMERA_VEZ = {
    "type": "text",
    "text": {
        "body": "OPCIÓN 1: PACIENTE DE PRIMERA VEZ\n\n1️⃣ Fertilidad\n2️⃣ Síndrome de Ovario Poliquístico\n3️⃣ Chequeo Anual\n4️⃣ Embarazo\n5️⃣ Otros"
    }
}

SERVICIOS_SUBSECUENTE = {
    "type": "text",
    "text": {
        "body": "OPCIÓN 2: PACIENTE SUBSECUENTE\n\n1️⃣ Fertilidad\n2️⃣ Síndrome de Ovario Poliquístico\n3️⃣ Chequeo Anual\n4️⃣ Embarazo\n5️⃣ Revisión de estudios\n6️⃣ Seguimiento folicular\n7️⃣ Otros"
    }
}

OTROS_OPCIONES = {
    "type": "text",
    "text": {
        "body": "Selecciona una opción:\n1️⃣ Espermatabioscopia directa\n2️⃣ Ginecología Pediátrica y Adolescentes\n3️⃣ Hablar con América"
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
        "body": "Estos son los horarios establecidos:\nLunes: 9:00 – 19:00 hrs (hora de comida 13:00 – 14:00 hrs)\nMartes: 9:00 - 11:00 hrs\nMiércoles: 15:00 – 20:00 hrs\nJueves: 9:00 – 12:00 hrs / 15:00 – 18:00 hrs\nViernes: 9:00 – 15:00 hrs\nSábado: 10:00 – 11:30 hrs (solo consultas de fertilidad y sop)"
    }
}

HORARIOS_SUBSECUENTE = {
    "type": "text",
    "text": {
        "body": "Da click para continuar Proceso de agenda\nLunes de 9:00 – 19:00 hrs (hora de comida 13:00 – 14:00 hrs)\nMartes 9:00 - 11:00 hrs\nMiércoles 15:00 – 20:00 hrs\nJueves 9:00 – 12:00 hrs / 15:00 – 18:00 hrs\nViernes 9:00 – 15:00 hrs\nSábado 8:00 – 15:00 hrs (solo consultas de infertilidad y sop)"
    }
}

COSTOS = {
    "type": "text",
    "text": {
        "body": "💰 Nuestros costos:\n\n• PAQUETE CHECK UP: El costo es de $1,800 pesos (incluye papanicolaou, USG, revisión de mamas, colposcopia y consulta)\n\n• CONSULTA DE FERTILIDAD: El costo es de $1,500 pesos. (incluye ultrasonido)\n\n• CONSULTA PRENATAL: El costo es de $1,500 pesos. (incluye ultrasonido)\n\n• ESPERMABIOTOSCOPIA: $1,500 pesos\n\n• ESPERMABIOTOSCOPIA CON FRAGMENTACIÓN: $4,500 pesos"
    }
}

CONFIRMACION_PRIMERA_VEZ = {
    "type": "text",
    "text": {
        "body": "✅ ¡Gracias por agendar tu cita con Milkiin! 🎉\n\n📅 En caso de cancelación, es necesario avisar con mínimo 72 horas de anticipación para poder realizar el reembolso del anticipo y reprogramar tu cita.\n\n⏳ Si no se cumple con este plazo, lamentablemente no podremos hacer el reembolso.\nAgradecemos tu comprensión y tu confianza.\nEstamos para acompañarte con profesionalismo y cariño en cada paso 🤍\n\n📍 Te esperamos en:\nInsurgentes Sur 1160, 6º piso, Colonia Del Valle.\n🗺️ Ubicación en Google Maps (https://maps.app.goo.gl/3A74a9K4w2T5L85K9)\n\n💳 Aceptamos pagos con tarjeta (incluyendo AMEX) y en efectivo.\nSi tienes alguna duda o necesitas apoyo adicional, no dudes en escribirnos.\n¡Será un gusto atenderte! 🤍"
    }
}

CONFIRMACION_SUBSECUENTE = {
    "type": "text",
    "text": {
        "body": "✅ ¡Gracias por agendar tu cita con Milkiin!\n\n📍 Te esperamos en:\nInsurgentes Sur 1160, 6º piso, Colonia Del Valle.\n🗺️ Ubicación en Google Maps (https://maps.app.goo.gl/3A74a9K4w2T5L85K9)\n\n💳 Aceptamos pagos con tarjeta (incluyendo AMEX) y en efectivo.\nSi tienes alguna duda o necesitas apoyo adicional, no dudes en escribirnos."
    }
}

PAGO_INFO = {
    "type": "text",
    "text": {
        "body": "Te compartimos una información importante:\n📌 Para consultas de primera vez, solicitamos un anticipo de $500 MXN.\nEl monto restante se cubrirá el día de tu consulta, una vez finalizada.\nEsta medida nos permite asegurar tu lugar, ya que contamos con alta demanda.\nFavor de enviar su comprobante de pago al correo milkiin.gine@gmail.com\nDatos para pago\nCuenta CLABE: 012 180 0048 4828712 2\nNum. Cuenta: 048 482 8712\nBanco: BBVA"
    }
}

FACTURACION_FORM = {
    "type": "text",
    "text": {
        "body": "Requiero factura\n-Por favor, completa el siguiente formulario con tus datos fiscales:\n📄Formulario de facturación (https://forms.gle/tuformulario)\nUna vez enviado, te haremos llegar tu factura en un plazo máximo de 72 horas hábiles.\n¡Gracias por tu preferencia!"
    }
}

FACTURACION_DUDAS = {
    "type": "text",
    "text": {
        "body": "Dudas sobre facturación\n-Puedes escribirnos directamente a:\n📬lcastillo@gbcasesoria.mx\nEstaremos encantados de ayudarte lo antes posible.\n¡Gracias por tu confianza!"
    }
}

RESULTADOS_INFO = {
    "type": "text",
    "text": {
        "body": "📑 Para el envío de resultados de análisis, por favor\nenvíalos al siguiente correo:\n📬gine.moni.og@gmail.com\nNos aseguraremos de revisarlos con oportunidad antes de tu consulta.\n¡Gracias por tu colaboración!"
    }
}

DUDAS_INFO = {
    "type": "text",
    "text": {
        "body": "💬 ¿Tienes alguna duda o necesitas asistencia personalizada?\nPor favor, escríbenos brevemente tu consulta y en unos momentos te conectaremos con un miembro de nuestro equipo.\n👩‍⚕️ Estamos aquí para ayudarte…"
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

# DURACIONES (en minutos)
DURACIONES_PRIMERA_VEZ = {
    "1": 90,  # Fertilidad
    "2": 60,  # SOP
    "3": 60,  # Chequeo Anual
    "4": 60,  # Embarazo
    "5": 30   # Otros (Espermatabioscopia, Ginecología Pediátrica)
}

DURACIONES_SUBSECUENTE = {
    "1": 45,  # Fertilidad
    "2": 45,  # SOP
    "3": 45,  # Chequeo Anual
    "4": 45,  # Embarazo
    "5": 30,  # Revisión de estudios
    "6": 30,  # Seguimiento folicular
    "7": 30   # Otros
}

# === FUNCIONES PARA WHATSAPP META API ===
def send_whatsapp_message(phone_number, message_data):
    """Envía mensaje usando WhatsApp Business API de Meta"""
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
            logger.info(f"✅ Mensaje enviado a {phone_number}")
            return response.json()
        else:
            logger.error(f"❌ Error API Meta: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"❌ Excepción al enviar mensaje: {e}")
        return None

def format_phone_number(phone):
    clean_phone = re.sub(r'\D', '', phone)
    if clean_phone.startswith('52') and len(clean_phone) == 12:
        return clean_phone
    elif clean_phone.startswith('1') and len(clean_phone) == 11:
        return '52' + clean_phone[1:]
    elif len(clean_phone) == 10:
        return '521' + clean_phone
    return clean_phone

def extract_user_data(message_body):
    data = {}
    lines = message_body.split('\n')
    for line in lines:
        if 'nombre' in line.lower() or 'paciente' in line.lower():
            if ':' in line:
                data['nombre'] = line.split(':', 1)[1].strip()
            else:
                data['nombre'] = line.strip()
        elif '@' in line and '.' in line:
            match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', line)
            if match:
                data['correo'] = match.group(0)
        elif re.search(r'\d{10,}', line):
            phone_match = re.search(r'\d{10,}', line)
            if phone_match:
                data['telefono'] = phone_match.group(0)
    return data

# === PROCESAMIENTO DE MENSAJES ===
def process_user_message(phone_number, message_body):
    user_data = user_state.get(phone_number, {"stage": "start"})
    user_info = user_data_storage.get(phone_number, {})

    logger.info(f"[MENSAJE ENTRANTE] {phone_number}: {message_body}")

    if message_body.lower() in ["hola", "hello", "hi", "iniciar", "empezar"] or user_data["stage"] == "start":
        send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        user_data["stage"] = "option_selected"
        user_state[phone_number] = user_data
        return

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
                "text": {"body": "1️⃣ Requiero factura\n2️⃣ Dudas sobre facturación"}
            })
        elif message_body == "5":
            send_whatsapp_message(phone_number, RESULTADOS_INFO)
            send_whatsapp_message(phone_number, WELCOME_MESSAGE)
            user_data["stage"] = "option_selected"
        elif message_body == "6":
            send_whatsapp_message(phone_number, DUDAS_INFO)
            user_data["stage"] = "dudas"
        else:
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, selecciona una opción válida del 1 al 6."}
            })

    # Flujo primera vez
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
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, elige una opción válida (1-5)."}
            })

    elif user_data["stage"] == "otros_opciones":
        if message_body in ["1", "2"]:
            user_data["servicio"] = message_body
            user_data["stage"] = "especialista"
            send_whatsapp_message(phone_number, ESPECIALISTAS)
        elif message_body == "3":
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Conectando con América... Un miembro del equipo te contactará pronto."}
            })
            user_data["stage"] = "start"
            send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        else:
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, elige una opción válida (1-3)."}
            })

    elif user_data["stage"] == "especialista":
        if message_body in ["1", "2", "3", "4", "5"]:
            user_data["especialista"] = message_body
            user_data["stage"] = "datos_paciente"
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, envía:\nNombre completo\nCorreo electrónico\nTeléfono\nFecha de nacimiento\nEdad"}
            })
        else:
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, elige una opción válida (1-5)."}
            })

    elif user_data["stage"] == "datos_paciente":
        extracted_data = extract_user_data(message_body)
        user_info.update(extracted_data)
        user_data_storage[phone_number] = user_info
        user_data["stage"] = "mostrar_horarios"
        send_whatsapp_message(phone_number, HORARIOS_PRIMERA_VEZ)
        send_whatsapp_message(phone_number, PAGO_INFO)
        send_whatsapp_message(phone_number, {
            "type": "text",
            "text": {"body": "Por favor, responde con la fecha y hora que prefieras (ej: 2025-04-05 10:00)"}
        })
        user_data["stage"] = "esperando_fecha"

    # Flujo subsecuente
    elif user_data["stage"] == "servicio_subsecuente":
        if message_body in ["1", "2", "3", "4", "5", "6"]:
            user_data["servicio"] = message_body
            user_data["stage"] = "datos_subsecuente"
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, envía:\nNombre completo\nCorreo electrónico\nTeléfono\nFecha de nacimiento\nEdad"}
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
            user_data["stage"] = "datos_subsecuente"
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, envía:\nNombre completo\nCorreo electrónico\nTeléfono\nFecha de nacimiento\nEdad"}
            })

    elif user_data["stage"] == "datos_subsecuente":
        extracted_data = extract_user_data(message_body)
        user_info.update(extracted_data)
        user_data_storage[phone_number] = user_info
        user_data["stage"] = "mostrar_horarios_sub"
        send_whatsapp_message(phone_number, HORARIOS_SUBSECUENTE)
        send_whatsapp_message(phone_number, {
            "type": "text",
            "text": {"body": "Por favor, responde con la fecha y hora que prefieras (ej: 2025-04-05 10:00)"}
        })
        user_data["stage"] = "esperando_fecha_sub"

    elif user_data["stage"] == "esperando_fecha":
        try:
            fecha_hora = datetime.strptime(message_body.strip(), "%Y-%m-%d %H:%M")
            servicio = user_data["servicio"]
            duracion = DURACIONES_PRIMERA_VEZ.get(servicio, 60)
            especialista = ESPECIALISTAS_NOMBRES.get(user_data["especialista"], "No definido")
            nombre_paciente = user_info.get('nombre', 'Paciente')
            servicio_nombre = SERVICIOS_NOMBRES.get(servicio, "Consulta")
            send_whatsapp_message(phone_number, CONFIRMACION_PRIMERA_VEZ)
            cita_detalle = {
                "type": "text",
                "text": {
                    "body": f"📅 CONFIRMACIÓN DE CITA\n\nPaciente: {nombre_paciente}\nServicio: {servicio_nombre}\nEspecialista: {especialista}\nFecha y hora: {message_body}\nDuración estimada: {duracion} minutos"
                }
            }
            send_whatsapp_message(phone_number, cita_detalle)
            user_data["stage"] = "start"
        except ValueError:
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, envía la fecha y hora en formato: AAAA-MM-DD HH:MM\nEj: 2025-04-05 10:00"}
            })

    elif user_data["stage"] == "esperando_fecha_sub":
        try:
            fecha_hora = datetime.strptime(message_body.strip(), "%Y-%m-%d %H:%M")
            servicio = user_data["servicio"]
            duracion = DURACIONES_SUBSECUENTE.get(servicio, 45)
            especialista = ESPECIALISTAS_NOMBRES.get("1", "Dra. Mónica Olavarría") # Asumiendo que siempre es Mónica Olavarría para subsecuentes si no se especifica
            nombre_paciente = user_info.get('nombre', 'Paciente')
            servicio_nombre = SERVICIOS_SUB_NOMBRES.get(servicio, "Consulta")
            send_whatsapp_message(phone_number, CONFIRMACION_SUBSECUENTE)
            cita_detalle = {
                "type": "text",
                "text": {
                    "body": f"📅 CONFIRMACIÓN DE CITA\n\nPaciente: {nombre_paciente}\nServicio: {servicio_nombre}\nEspecialista: {especialista}\nFecha y hora: {message_body}\nDuración estimada: {duracion} minutos"
                }
            }
            send_whatsapp_message(phone_number, cita_detalle)
            user_data["stage"] = "start"
        except ValueError:
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, envía la fecha y hora en formato: AAAA-MM-DD HH:MM\nEj: 2025-04-05 10:00"}
            })

    elif user_data["stage"] == "atencion_cliente":
        if message_body == "1":
            send_whatsapp_message(phone_number, COSTOS)
        elif message_body == "2":
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Conectando con América... Un miembro del equipo te contactará pronto."}
            })
        send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        user_data["stage"] = "option_selected"

    elif user_data["stage"] == "facturacion":
        if message_body == "1":
            send_whatsapp_message(phone_number, FACTURACION_FORM)
        elif message_body == "2":
            send_whatsapp_message(phone_number, FACTURACION_DUDAS)
        send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        user_data["stage"] = "option_selected"

    elif user_data["stage"] == "dudas":
        logger.info(f"[DUDA] {phone_number}: {message_body}")
        send_whatsapp_message(phone_number, {
            "type": "text",
            "text": {"body": "Hemos recibido tu consulta. Un miembro del equipo te responderá pronto."}
        })
        send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        user_data["stage"] = "option_selected"

    else:
        send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        user_data["stage"] = "option_selected"

    user_state[phone_number] = user_data

# === WEBHOOKS ===
@application.route('/webhook/', methods=['GET', 'POST'])
def webhook():
    logger.info("📥 [LOG] Petición recibida en /webhook/")
    logger.info(f"📌 Método: {request.method}")
    logger.info(f"📌 Args: {request.args}")
    logger.info(f"📌 Remote IP: {request.remote_addr}")

    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        logger.info(f"🔍 Modo: {mode}, Token: {token}")

        if mode == 'subscribe' and token == META_VERIFY_TOKEN:
            logger.info("✅ Webhook verificado exitosamente")
            return challenge, 200, {'Content-Type': 'text/plain'}
        else:
            logger.warning("❌ Verificación fallida")
            return 'Forbidden', 403

    elif request.method == 'POST':
        try:
            data = request.get_json()
            logger.info(f"📥 Datos POST: {json.dumps(data, indent=2)}")

            if data.get('entry'):
                for entry in data['entry']:
                    if entry.get('changes'):
                        for change in entry['changes']:
                            if change.get('value') and change['value'].get('messages'):
                                messages = change['value']['messages']
                                for message in messages:
                                    if message.get('type') == 'text':
                                        phone_number = message['from']
                                        message_body = message['text']['body']
                                        process_user_message(phone_number, message_body)

            return 'EVENT_RECEIVED', 200
        except Exception as e:
            logger.error(f"❌ Error en POST: {e}")
            return 'Error', 500


@application.route('/')
def home():
    return jsonify({
        "message": "🤖 Bot de WhatsApp para Milkiin usando Meta API está activo",
        "status": "✅ Online",
        "version": "1.0.0"
    })


@application.route('/test/')
def test():
    return jsonify({"status": "ok", "message": "Ruta /test/ funciona correctamente"})


# Manejador de rutas no encontradas
@application.errorhandler(404)
def not_found(e):
    logger.warning(f"⚠️ 404 - Ruta no encontrada: {request.path}")
    return jsonify({"error": "Ruta no encontrada", "path": request.path}), 404


# No uses if __name__ == "__main__" en CPanel
# Passenger lo maneja automáticamente