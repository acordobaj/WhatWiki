from flask import Flask, request, jsonify
import requests
import json
import re
from datetime import datetime
import os

# Crear la aplicación Flask (cambiar 'app' por 'application' para Passenger)
application = Flask(__name__)

# === CONFIGURACIÓN ===
META_ACCESS_TOKEN = os.environ.get('META_ACCESS_TOKEN') or 'temporal_token_placeholder'
META_PHONE_NUMBER_ID = os.environ.get('META_PHONE_NUMBER_ID') or '123456789012345'
META_VERIFY_TOKEN = os.environ.get('META_VERIFY_TOKEN') or 'milkiin_verify_token_2024'

# === ESTADO DE CONVERSACIÓN ===
user_state = {}
user_data_storage = {}

# === MENSAJES DEL BOT ===
WELCOME_MESSAGE = {
    "type": "text",
    "text": {
        "body": "¡Hola! Bienvenido(a) a Milkiin, donde cada paso en tu camino a la maternidad cuenta.\n\nSoy MilkiBot, tu asistente virtual, y estoy aquí para ayudarte con todo lo que necesites.\n\n¿En qué te puedo apoyar hoy?\n1️⃣ Paciente de primera vez\n2️⃣ Paciente subsecuente\n3️⃣ Atención al cliente\n4️⃣ Facturación\n5️⃣ Envío de Resultados\n6️⃣ Dudas"
    }
}

# SERVICIOS PRIMERA VEZ
SERVICIOS_PRIMERA_VEZ = {
    "type": "text",
    "text": {
        "body": "Selecciona el servicio de primera vez:\n1️⃣ Fertilidad\n2️⃣ Síndrome de Ovario Poliquístico\n3️⃣ Chequeo Anual\n4️⃣ Embarazo\n5️⃣ Otros"
    }
}

# SERVICIOS SUBSECUENTE
SERVICIOS_SUBSECUENTE = {
    "type": "text",
    "text": {
        "body": "Selecciona el servicio subsecuente:\n1️⃣ Fertilidad\n2️⃣ Síndrome de Ovario Poliquístico\n3️⃣ Chequeo Anual\n4️⃣ Embarazo\n5️⃣ Revisión de estudios\n6️⃣ Seguimiento folicular\n7️⃣ Otros"
    }
}

# SUBOPCIONES "OTROS"
OTROS_OPCIONES = {
    "type": "text",
    "text": {
        "body": "Selecciona una opción:\n1️⃣ Espermabiopsia directa\n2️⃣ Ginecología Pediátrica y Adolescentes\n3️⃣ Hablar con América"
    }
}

# ESPECIALISTAS
ESPECIALISTAS = {
    "type": "text",
    "text": {
        "body": "Selecciona tu especialista:\n1️⃣ Dra. Mónica Olavarría\n2️⃣ Dra. Graciela Guadarrama\n3️⃣ Dra. Cinthia Ruiz\n4️⃣ Dra. Gisela Cuevas\n5️⃣ Dra. Gabriela Sánchez"
    }
}

# HORARIOS
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

# COSTOS
COSTOS = {
    "type": "text",
    "text": {
        "body": "💰 Nuestros costos:\n• PAQUETE CHECK UP: $1,800 pesos\n• CONSULTA DE FERTILIDAD: $1,500 pesos\n• CONSULTA PRENATAL: $1,500 pesos\n• ESPERMABIOTOSCOPIA: $1,500 pesos\n• CON FRAGMENTACIÓN: $4,500 pesos"
    }
}

# CONFIRMACIÓN FINAL
CONFIRMACION = {
    "type": "text",
    "text": {
        "body": "¡Gracias por agendar tu cita con Milkiin! 🎉\n\n📍 Te esperamos en:\nInsurgentes Sur 1160, 6º piso, Colonia Del Valle.\n\n💳 Aceptamos pagos con tarjeta (incluyendo AMEX) y en efectivo.\n\n⏰ Recordatorio importante:\nEn caso de cancelación, es necesario avisar con mínimo 72 horas de anticipación para poder realizar el reembolso del anticipo y reprogramar tu cita.\n\nAgradecemos tu comprensión y tu confianza. ❤️"
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
    "5": 30   # Otros
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
        # CORREGIDO: Eliminar espacio extra
        url = f"https://graph.facebook.com/v22.0/{META_PHONE_NUMBER_ID}/messages"
        
        headers = {
            'Authorization': f'Bearer {META_ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        # Formatear el número de teléfono
        formatted_phone = format_phone_number(phone_number)
        
        payload = {
            "messaging_product": "whatsapp",
            "to": formatted_phone,
            "type": message_data["type"]
        }
        
        # Agregar el contenido del mensaje
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
    """Formatea número de teléfono para WhatsApp API"""
    # Eliminar caracteres no numéricos
    clean_phone = re.sub(r'\D', '', phone)
    
    # Asegurar formato correcto
    if clean_phone.startswith('52') and len(clean_phone) == 12:
        return clean_phone
    elif clean_phone.startswith('1') and len(clean_phone) == 11:
        return '52' + clean_phone[1:]
    elif len(clean_phone) == 10:
        return '521' + clean_phone
    return clean_phone

def extract_user_data(message_body):
    """Extrae datos del paciente del mensaje"""
    data = {}
    lines = message_body.split('\n')
    
    for line in lines:
        if 'nombre' in line.lower() or 'paciente' in line.lower():
            data['nombre'] = line.split(':', 1)[1].strip() if ':' in line else line
        elif '@' in line and '.' in line:
            # Buscar correo
            match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', line)
            if match:
                data['correo'] = match.group(0)
        elif re.search(r'\d{10,}', line):
            # Buscar teléfono
            phone_match = re.search(r'\d{10,}', line)
            if phone_match:
                data['telefono'] = phone_match.group(0)
    
    return data

# === FUNCIONES DE PROCESAMIENTO ===

def process_user_message(phone_number, message_body):
    """Procesa mensajes usando la lógica del bot"""
    user_data = user_state.get(phone_number, {"stage": "start"})
    user_info = user_data_storage.get(phone_number, {})
    
    print(f"[MENSAJE ENTRANTE] {phone_number}: {message_body}")
    
    # === FLUJO PRINCIPAL ===
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
                "text": {"body": "Para el envío de resultados, envíalos al correo:\n📧 gine.moni.og@gmail.com"}
            })
            send_whatsapp_message(phone_number, WELCOME_MESSAGE)
            user_data["stage"] = "option_selected"
        elif message_body == "6":
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "¿Tienes alguna duda? Escríbenos brevemente tu consulta y en breve te conectaremos con un miembro del equipo."}
            })
            user_data["stage"] = "dudas"
        else:
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, selecciona una opción válida del 1 al 6."}
            })
    
    # === PRIMERA VEZ ===
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
                "text": {"body": "Por favor, envía:\nNombre completo\nCorreo electrónico\nTeléfono\nFecha de nacimiento\nEdad"}
            })
        else:
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, elige una opción válida (1-5)."}
            })
    
    elif user_data["stage"] == "datos_paciente":
        # Extraer datos del paciente
        extracted_data = extract_user_data(message_body)
        user_info.update(extracted_data)
        user_data_storage[phone_number] = user_info
        
        user_data["stage"] = "mostrar_horarios"
        send_whatsapp_message(phone_number, HORARIOS_PRIMERA_VEZ)
        
        # Enviar información de pago
        pago_info = {
            "type": "text",
            "text": {
                "body": "Te compartimos una información importante:\n\nPara consultas de primera vez, solicitamos un anticipo de $500 MXN.\n\nDatos para pago:\nBanco: BBVA\nCuenta: 048 482 8712\nCLABE: 012180004848287122\n\nFavor de enviar comprobante a: milkiin.gine@gmail.com"
            }
        }
        send_whatsapp_message(phone_number, pago_info)
        
        user_data["stage"] = "esperando_fecha"
    
    # === SUBSECUENTE ===
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
        # Extraer datos del paciente
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
    
    # === AGENDAR CITA (PRIMERA VEZ) ===
    elif user_data["stage"] == "esperando_fecha":
        try:
            fecha_hora = datetime.strptime(message_body.strip(), "%Y-%m-%d %H:%M")
            
            servicio = user_data["servicio"]
            duracion = DURACIONES_PRIMERA_VEZ.get(servicio, 60)
            especialista = ESPECIALISTAS_NOMBRES.get(user_data["especialista"], "No definido")
            nombre_paciente = user_info.get('nombre', 'Paciente')
            servicio_nombre = SERVICIOS_NOMBRES.get(servicio, "Consulta")
            
            # Enviar confirmación
            send_whatsapp_message(phone_number, CONFIRMACION)
            
            # Enviar detalles de la cita
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
    
    # === AGENDAR CITA (SUBSECUENTE) ===
    elif user_data["stage"] == "esperando_fecha_sub":
        try:
            fecha_hora = datetime.strptime(message_body.strip(), "%Y-%m-%d %H:%M")
            
            servicio = user_data["servicio"]
            duracion = DURACIONES_SUBSECUENTE.get(servicio, 45)
            especialista = ESPECIALISTAS_NOMBRES.get("1", "Dra. Mónica Olavarría")
            nombre_paciente = user_info.get('nombre', 'Paciente')
            servicio_nombre = SERVICIOS_SUB_NOMBRES.get(servicio, "Consulta")
            
            # Enviar confirmación
            send_whatsapp_message(phone_number, CONFIRMACION)
            
            # Enviar detalles de la cita
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
    
    # === ATENCIÓN AL CLIENTE ===
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
    
    # === FACTURACIÓN ===
    elif user_data["stage"] == "facturacion":
        if message_body == "1":
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Por favor, completa el formulario:\n🔗 [Formulario de facturación](https://forms.gle/tuformulario)"}
            })
        elif message_body == "2":
            send_whatsapp_message(phone_number, {
                "type": "text",
                "text": {"body": "Para dudas de facturación, escribe a:\n📧 lcastillo@gbcasesoria.mx"}
            })
        send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        user_data["stage"] = "option_selected"
    
    # === DUDAS ===
    elif user_data["stage"] == "dudas":
        print(f"[DUDA] {phone_number}: {message_body}")
        send_whatsapp_message(phone_number, {
            "type": "text",
            "text": {"body": "Hemos recibido tu consulta. Un miembro del equipo te responderá pronto."}
        })
        send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        user_data["stage"] = "option_selected"
    
    else:
        send_whatsapp_message(phone_number, WELCOME_MESSAGE)
        user_data["stage"] = "option_selected"
    
    # Guardar estado
    user_state[phone_number] = user_data

# === WEBHOOKS DE META ===

@application.route('/webhook/', methods=['GET', 'POST']) # <--- MODIFICACIÓN CRÍTICA
def webhook():
    """Webhook para recibir mensajes de WhatsApp Meta API"""
    if request.method == 'GET':
        # Verificación inicial de webhook
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        print(f"📥 Verificación de Webhook - Modo: {mode}, Token: {token}")
        
        if mode and token:
            if mode == 'subscribe' and token == META_VERIFY_TOKEN:
                print('✅ WEBHOOK_VERIFICADO')
                return challenge
            else:
                return 'Verificación fallida', 403
    
    elif request.method == 'POST':
        # Procesar mensajes entrantes
        try:
            data = request.get_json()
            print(f"📥 Datos recibidos: {json.dumps(data, indent=2)}")
            
            if data.get('entry'):
                for entry in data['entry']:
                    if entry.get('changes'):
                        for change in entry['changes']:
                            if change.get('value') and change['value'].get('messages'):
                                messages = change['value']['messages']
                                for message in messages:
                                    phone_number = message['from']
                                    message_body = message.get('text', {}).get('body', '')
                                    
                                    # Procesar el mensaje
                                    process_user_message(phone_number, message_body)
            
            return 'EVENT_RECEIVED', 200
            
        except Exception as e:
            print(f"❌ Error en webhook: {e}")
            return 'Error', 500

@application.route('/send-test-message', methods=['POST'])
def send_test_message():
    """Endpoint para enviar mensajes de prueba"""
    try:
        data = request.get_json()
        phone = data.get('phone')
        message = data.get('message', 'Mensaje de prueba desde Milkiin Bot')
        
        if not phone:
            return jsonify({"error": "Número de teléfono requerido"}), 400
        
        result = send_whatsapp_message(phone, {
            "type": "text",
            "text": {"body": message}
        })
        
        return jsonify({"success": True, "result": result})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@application.route('/')
def home():
    return jsonify({
        "message": "🤖 Bot de WhatsApp para Milkiin usando Meta API está activo",
        "status": "✅ Online",
        "version": "1.0.0"
    })

# Para debugging - endpoint de prueba
@application.route('/test-webhook')
def test_webhook():
    return jsonify({
        "message": "Webhook endpoint disponible",
        "endpoint": "/webhook",
        "methods": ["GET", "POST"]
    })


if __name__ == "__main__":
    pass