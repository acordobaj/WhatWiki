# application.py
from flask import Flask, request, jsonify
import requests
import json
import re
from datetime import datetime, timedelta
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
META_PHONE_NUMBER_ID = os.environ.get('META_PHONE_NUMBER_ID', '799601806561220')
META_VERIFY_TOKEN = os.environ.get('META_VERIFY_TOKEN')

# Valores por defecto (solo para desarrollo - ¡no usar en producción!)
if not META_ACCESS_TOKEN:
    logger.warning("⚠️ META_ACCESS_TOKEN no definido. Usando valor temporal.")
    META_ACCESS_TOKEN = "EAAB..."  # Reemplaza con tu token real

if not META_PHONE_NUMBER_ID:
    logger.warning("⚠️ META_PHONE_NUMBER_ID no definido.")
    META_PHONE_NUMBER_ID = "799601806561220"

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
        "body": "👋 ¡Hola! Bienvenido(a) a Milkiin, donde cada paso en tu camino a la maternidad cuenta.\n✨ Soy MilkiBot, tu asistente virtual, y estoy aquí para ayudarte con todo lo que necesites.\n\n¿En qué te puedo apoyar hoy?\n1- Paciente de primera vez\n2- Paciente subsecuente\n3- Atención al cliente\n4- Facturación\n5- Envío de Resultados\n6- Dudas\n\nPor favor, selecciona una opción para comenzar..."
    }
}

SERVICIOS_PRIMERA_VEZ = {
    "type": "text",
    "text": {
        "body": "Selecciona el servicio de primera vez:\n1- Fertilidad\n2- Síndrome de Ovario Poliquístico\n3- Chequeo Anual\n4- Embarazo\n5- Otros"
    }
}

SERVICIOS_SUBSECUENTE = {
    "type": "text",
    "text": {
        "body": "Selecciona el servicio subsecuente:\n1- Fertilidad\n2- Síndrome de Ovario Poliquístico\n3- Chequeo Anual\n4- Embarazo\n5- Revisión de estudios\n6- Seguimiento folicular\n7- Otros"
    }
}

OTROS_OPCIONES = {
    "type": "text",
    "text": {
        "body": "Selecciona una opción:\n1- Espermatabioscopia directa\n2- Ginecología Pediátrica y Adolescentes\n3- Hablar con América"
    }
}

ESPECIALISTAS = {
    "type": "text",
    "text": {
        "body": "Selecciona tu especialista:\n1- Dra. Mónica Olavarría\n2- Dra. Graciela Guadarrama\n3- Dra. Cinthia Ruiz\n4- Dra. Gisela Cuevas\n5- Dra. Gabriela Sánchez"
    }
}

HORARIOS_PRIMERA_VEZ = {
    "type": "text",
    "text": {
        "body": "Estos son los horarios establecidos:\nLunes de 9:00-19:00 hrs (hora de comida 13:00-14:00 hrs)\nMartes 9:00-11:00 hrs\nMiércoles 15:00-20:00 hrs\nJueves 9:00-12:00 hrs / 15:00-18:00 hrs\nViernes 9:00-15:00 hrs\nSábado 10:00-11:30 hrs (solo consultas de fertilidad y sop)"
    }
}

HORARIOS_SUBSECUENTE = {
    "type": "text",
    "text": {
        "body": "Estos son los horarios establecidos:\nLunes de 9:00-19:00 hrs (hora de comida 13:00-14:00 hrs)\nMartes 9:00-11:00 hrs\nMiércoles 15:00-20:00 hrs\nJueves 9:00-12:00 hrs / 15:00-18:00 hrs\nViernes 9:00-15:00 hrs\nSábado 8:00-15:00 hrs (solo consultas de infertilidad y sop)"
    }
}

COSTOS = {
    "type": "text",
    "text": {
        "body": "💰 Nuestros costos:\n• PAQUETE CHECK UP: El costo es de $1,800 pesos (incluye papanicolaou, USG, revisión de mamas, colposcopia y consulta)\n• CONSULTA DE FERTILIDAD: El costo es de $1,500 pesos. (incluye ultrasonido)\n• CONSULTA PRENATAL: El costo es de $1,500 pesos. (incluye ultrasonido)\n• ESPERMABIOTOSCOPIA: $1,500 pesos\n• ESPERMABIOTOSCOPIA CON FRAGMENTACIÓN: $4,500 pesos\n\nPara otros costos (hablar con America)"
    }
}

CONFIRMACION = {
    "type": "text",
    "text": {
        "body": "✅ ¡Gracias por agendar tu cita con Milkiin!\n\n📍 Te esperamos en: Insurgentes Sur 1160, 6º piso, Colonia Del Valle. 🗺️ Ubicación en Google Maps\n\n💳 Aceptamos pagos con tarjeta (incluyendo AMEX) y en efectivo."
    }
}

INFO_IMPORTANTE = {
    "type": "text",
    "text": {
        "body": "Te compartimos una información importante: 📌 Para consultas de primera vez, solicitamos un anticipo de $500 MXN.\nEl monto restante se cubrirá el día de tu consulta, una vez finalizada.\nEsta medida nos permite asegurar tu lugar, ya que contamos con alta demanda.\n\nDatos para pago:\nBanco: BBVA\nCuenta: 048 482 8712\nCLABE: 012 180 0048 4828712 2\n\nFavor de enviar su comprobante de pago al correo milkiin.gine@gmail.com"
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
    "1": 90, # Fertilidad
    "2": 60, # SOP
    "3": 60, # Chequeo Anual
    "4": 60, # Embarazo
    "5": 30  # Otros
}

DURACIONES_SUBSECUENTE = {
    "1": 45, # Fertilidad (general)
    "2": 45, # SOP
    "3": 45, # Chequeo Anual
    "4": 45, # Embarazo
    "5": 30, # Revisión de estudios
    "6": 30, # Seguimiento folicular
    "7": 30  # Otros
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
    
    # ✅ Lógica para manejar entrada separada por comas en una sola línea
    if len(lines) == 1 and ',' in lines[0]:
        parts = lines[0].split(',')
        if len(parts) >= 1:
            data['nombre'] = parts[0].strip()
        if len(parts) >= 2:
            data['correo'] = parts[1].strip()
        if len(parts) >= 3:
            data['telefono'] = parts[2].strip()
        # La lógica actual no extrae fecha y edad de la misma línea, solo las solicita
    else:
        # Lógica original para manejar líneas separadas por saltos de línea
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
                "text": {"body": "1- COSTOS\n2- Hablar con America"}
            })
        elif message_body == "4":
            user_data["stage"] = "facturacion"
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "1- Requiero factura\n2- Dudas"}
            })
        elif message_body == "5":
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "📑 Para el envío de resultados de análisis, por favor envíalos al siguiente correo: 📬 gine.moni.og@gmail.com\n\nNos aseguraremos de revisarlos con oportunidad antes de tu consulta. ¡Gracias por tu colaboración!"}
            })
            send_whatsapp_message(phone_number, WELCOME_MESSAGE)
            user_data["stage"] = "option_selected"
        elif message_body == "6":
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "💬 ¿Tienes alguna duda o necesitas asistencia personalizada?\n\nPor favor, escríbenos brevemente tu consulta y en unos momentos te conectaremos con un miembro de nuestro equipo.\n\n👩‍⚕️ Estamos aquí para ayudarte..."}
            })
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
        if message_body == "3":
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Conectando con América... Un miembro del equipo te contactará pronto."}
            })
            user_data["stage"] = "start"
            send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        else:
            user_data["stage"] = "especialista"
            send_whatsapp_message(phone_number, ESPECIALISTAS)

    elif user_data["stage"] == "especialista":
        if message_body in ["1", "2", "3", "4", "5"]:
            user_data["especialista"] = message_body
            user_data["stage"] = "datos_paciente"
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, envía:\nNombre completo\nCorreo electrónico\nTeléfono\nFecha de nacimiento\nEdad\n\n*Recuerda que también puedes enviarlo en una sola línea separado por comas."}
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
        send_whatsapp_message(phone_number, INFO_IMPORTANTE)
        user_data["stage"] = "esperando_fecha"

    # Flujo subsecuente
    elif user_data["stage"] == "servicio_subsecuente":
        if message_body in ["1", "2", "3", "4", "5", "6"]:
            user_data["servicio"] = message_body
            user_data["stage"] = "datos_subsecuente"
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, envía:\nNombre completo\nCorreo electrónico\nTeléfono\nFecha de nacimiento\nEdad\n\n*Recuerda que también puedes enviarlo en una sola línea separado por comas."}
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
                "text": {"body": "Por favor, envía:\nNombre completo\nCorreo electrónico\nTeléfono\nFecha de nacimiento\nEdad\n\n*Recuerda que también puedes enviarlo en una sola línea separado por comas."}
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
            
            # ✅ Enviar mensajes de confirmación (sin el enlace del calendario)
            send_whatsapp_message(phone_number, CONFIRMACION)
            
            cancelacion_info = {
                "type": "text",
                "text": {
                    "body": "📅 En caso de cancelación, es necesario avisar con mínimo 72 horas de anticipación para poder realizar el reembolso del anticipo y reprogramar tu cita. ⏳ Si no se cumple con este plazo, lamentablemente no podremos hacer el reembolso.\n\nAgradecemos tu comprensión y tu confianza. Estamos para acompañarte con profesionalismo y cariño en cada paso 🤍\n\nSi tienes alguna duda o necesitas apoyo adicional, no dudes en escribirnos. ¡Será un gusto atenderte! 🤍"
                }
            }
            send_whatsapp_message(phone_number, cancelacion_info)

            # Este es el mensaje de detalle de la cita
            cita_detalle = {
                "type": "text",
                "text": {
                    "body": f"📅 CONFIRMACIÓN DE CITA\n\nServicio: {SERVICIOS_NOMBRES.get(servicio, 'Consulta')}\nEspecialista: {especialista}\nFecha y hora: {message_body}\nDuración estimada: {duracion} minutos"
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
            especialista = ESPECIALISTAS_NOMBRES.get("1", "Dra. Mónica Olavarría")
            
            # ✅ Enviar mensajes de confirmación (sin el enlace del calendario)
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "✅ ¡Gracias por agendar tu cita con Milkiin!\n\n📍 Te esperamos en: Insurgentes Sur 1160, 6º piso, Colonia Del Valle. 🗺️ Ubicación en Google Maps\n\n💳 Aceptamos pagos con tarjeta (incluyendo AMEX) y en efectivo.\n\nSi tienes alguna duda o necesitas apoyo adicional, no dudes en escribirnos."}
            })
            
            # Este es el mensaje de detalle de la cita
            cita_detalle = {
                "type": "text",
                "text": {
                    "body": f"📅 CONFIRMACIÓN DE CITA\n\nServicio: {SERVICIOS_SUB_NOMBRES.get(servicio, 'Consulta')}\nEspecialista: {especialista}\nFecha y hora: {message_body}\nDuración estimada: {duracion} minutos"
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
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "📄 Por favor, completa el siguiente formulario con tus datos fiscales: 🔗 [Formulario de facturación](https://docs.google.com/forms/d/e/1FAIpQLSfr1WWXWQGx4sZj3_0FnIp6XWBb1mol4GfVGfymflsRI0E5pA/viewform)\n\nUna vez enviado, te haremos llegar tu factura en un plazo máximo de 72 horas hábiles. ¡Gracias por tu preferencia!"}
            })
        elif message_body == "2":
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "📬 Para dudas de facturación, puedes escribirnos directamente a: lcastillo@gbcasesoria.mx\n\nEstaremos encantados de ayudarte lo antes posible. ¡Gracias por tu confianza!"}
            })
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