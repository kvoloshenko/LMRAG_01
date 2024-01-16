import re
import os
from langchain.text_splitter import CharacterTextSplitter
from langchain.docstore.document import Document
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
import openai
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta, timezone
import tools_01 as tls

# XML теги для лога
LOG_S = '<log>'
LOG_E = '</log>'
X_CDATA_S = '<![CDATA['
X_CDATA_E = ']]>'
PROMPT_S = '<prompt>' + X_CDATA_S
PROMPT_E = X_CDATA_E + '</prompt>'
KNOWLEDGE_DB_S = '<kdb>' + X_CDATA_S
KNOWLEDGE_DB_E = X_CDATA_E + '</kdb>'
MESSAGE_CONTENT_S = '<mc>' + X_CDATA_S
MESSAGE_CONTENT_E = X_CDATA_E + '</mc>'
NUM_TOKENS_S = '<num_tokens>'
NUM_TOKENS_E = '</num_tokens>'
CHUNK_NUM_S = '<chunk_num>'
CHUNK_NUM_E = '</chunk_num>'
MESSAGES_S = '<messages>' + X_CDATA_S
MESSAGES_E = X_CDATA_E + '</messages>'
COMPLETION_S = '<completion>' + X_CDATA_S
COMPLETION_E = X_CDATA_E + '</completion>'


# Get the current date and time
current_datetime = datetime.now(tz=timezone(timedelta(hours=3)))

# Format the date and time as a string
formatted_datetime = current_datetime.strftime("%Y-%m-%d_%H-%M-%S")

logfilename = "Logs/" + formatted_datetime + "_tgbot_gpt.xml"
csvfilename = "Logs/" + formatted_datetime + "_answers.csv"
logging.getLogger("faiss").setLevel(logging.ERROR)
logging.basicConfig(level=logging.INFO, filename=logfilename,filemode="w")

load_dotenv()
# Загрузка значений из .env
API_KEY = os.environ.get("API_KEY")
os.environ["OPENAI_API_KEY"] = API_KEY
openai.api_key = API_KEY

PROMPT = None
KNOWLEDGE_BASE = None

DATA_FILES = os.environ.get("DATA_FILES")
print (f'DATA_FILES = {DATA_FILES}')

if DATA_FILES == 'local':
    SYSTEM_DOC_LOCAL = os.environ.get("SYSTEM_DOC_LOCAL")
    print(f'SYSTEM_DOC_LOCAL={SYSTEM_DOC_LOCAL}')
    KNOWLEDGE_BASE_LOCAL = os.environ.get("KNOWLEDGE_BASE_LOCAL")
    print(f'KNOWLEDGE_BASE_LOCAL={KNOWLEDGE_BASE_LOCAL}')

logging.info(LOG_S)
LL_MODEL = os.environ.get("LL_MODEL") # модель
logging.info(f'LL_MODEL = {LL_MODEL}')
print(f'LL_MODEL = {LL_MODEL}')

CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE")) # Количество токинов в  чанке
logging.info(f'CHUNK_SIZE={CHUNK_SIZE}')
print(f'CHUNK_SIZE={CHUNK_SIZE}')

NUMBER_RELEVANT_CHUNKS = int(os.environ.get("NUMBER_RELEVANT_CHUNKS"))   # Количество релевантных чанков
logging.info(f'NUMBER_RELEVANT_CHUNKS={NUMBER_RELEVANT_CHUNKS}')

TEMPERATURE = float(os.environ.get("TEMPERATURE")) # Температура модели
logging.info(f'TEMPERATURE={TEMPERATURE}')
print(f'TEMPERATURE={TEMPERATURE}')

SYSTEM_DOC_URL = os.environ.get("SYSTEM_DOC_URL") # промпт
print(f'SYSTEM_DOC_URL = {SYSTEM_DOC_URL}')
logging.info(f'SYSTEM_DOC_URL = {SYSTEM_DOC_URL}')

KNOWLEDGE_BASE_URL = os.environ.get("KNOWLEDGE_BASE_URL") # база знаний
print(f'KNOWLEDGE_BASE_URL = {KNOWLEDGE_BASE_URL}')
logging.info(f'KNOWLEDGE_BASE_URL = {KNOWLEDGE_BASE_URL}')


# Записывам в файл заголовок
tls.write_to_file('user_id;user_name;question;answer', csvfilename)

def reload_data():
    print('reload_data')
    # Инструкция для GPT, которая будет подаваться в system
    if DATA_FILES == 'local':
        prompt = tls.load_text(SYSTEM_DOC_LOCAL)
    else:
        prompt = tls.load_document_text(SYSTEM_DOC_URL)  # Загрузка файла с Промтом
    logging.info(f'{PROMPT_S}{prompt}{PROMPT_E}')

    knowledge_base = create_index_db()
    return prompt, knowledge_base


# Функция создания индексной базы знаний
def create_index_db():
    # База знаний, которая будет подаваться в LangChain
    if DATA_FILES == 'local':
        database = tls.load_text(KNOWLEDGE_BASE_LOCAL)
    else:
        database = tls.load_document_text(KNOWLEDGE_BASE_URL)  # Загрузка файла с Базой Знаний
    logging.info(f'{KNOWLEDGE_DB_S}{database}{KNOWLEDGE_DB_E}')

    source_chunks = []
    splitter = CharacterTextSplitter(separator="\n", chunk_size=CHUNK_SIZE, chunk_overlap=0)

    for chunk in splitter.split_text(database):
        source_chunks.append(Document(page_content=chunk, metadata={}))

    chunk_num = len(source_chunks)
    print(f'chunk_num={chunk_num}')
    logging.info(f'{CHUNK_NUM_S}{chunk_num}{CHUNK_NUM_E}')

    # Инициализирум модель эмбеддингов
    embeddings = OpenAIEmbeddings()

    try:
        db = FAISS.from_documents(source_chunks, embeddings) # Создадим индексную базу из разделенных фрагментов текста
    except Exception as e: # обработка ошибок openai.error.RateLimitError
        print(f'!!! External error: {str(e)}')
        logging.error(f'!!! External error: {str(e)}')

    for chunk in source_chunks:  # Поиск слишком больших чанков
        if len(chunk.page_content) > CHUNK_SIZE:
            logging.warning(f'*** Слишком большой кусок! ***')
            logging.warning(f'chunk_len ={len(chunk.page_content)}')
            logging.warning(f'content ={chunk.page_content}')
            print(f'*** Слишком большой кусок! ***')
            print(f'chunk_len ={len(chunk.page_content)}')
            print(f'content ={chunk.page_content}')

    return db


PROMPT, KNOWLEDGE_BASE = reload_data()

# Запрос в ChatGPT
def get_answer(topic, user_id, user_name):

    # Поиск релевантных отрезков из базы знаний
    docs = KNOWLEDGE_BASE.similarity_search(topic, k = NUMBER_RELEVANT_CHUNKS)

    message_content = re.sub(r'\n{2}', ' ', '\n '.join([f'\n#### Document excerpt №{i+1}####\n' + doc.page_content + '\n' for i, doc in enumerate(docs)]))
    logging.info(f'{MESSAGE_CONTENT_S}{message_content}{MESSAGE_CONTENT_E}')

    messages = [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": f"Here is the document with information to respond to the client: {message_content}\n\n Here is the client's question: \n{topic}"}
    ]

    logging.info(f'{MESSAGES_S}{messages}{MESSAGES_E}')
    num_tokens = tls.num_tokens_from_messages(messages, LL_MODEL)
    logging.info(f'{NUM_TOKENS_S}{num_tokens}{NUM_TOKENS_E}')
    print(f'num_tokens = {num_tokens}')

    try:
        completion = openai.ChatCompletion.create(
            model=LL_MODEL,
            messages=messages,
            temperature=TEMPERATURE
        )
    except Exception as e:  # обработка ошибок openai.error.RateLimitError
        print(f'!!! External error: {str(e)}')
        logging.error(f'!!! External error: {str(e)}')

    logging.info(f'{COMPLETION_S}{completion}{COMPLETION_E}')
    answer = completion.choices[0].message.content
    line_for_file = '"' + user_id + '";"' + user_name + '";"' + topic + '";"' + answer + '"'
    tls.append_to_file(line_for_file, csvfilename)

    return answer, completion  # возвращает ответ

def answer_user_question(topic, user_name='UserName', user_id='000000'):
    ans, completion = get_answer(topic, user_id, user_name)  # получите ответ модели
    print(f'ans={ans}')

    return ans


if __name__ == '__main__':
    topic = 'Привет! Ты кто?'
    print(f'topic={topic}')
    response = answer_user_question(topic)
    print(f'response={response}')





