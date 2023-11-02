from flask import Flask, render_template, request
import rag_gpt_01 as rag_gpt
import rag_lm_01 as rag_lm

app = Flask(__name__)

@app.route("/")
def root():
    return render_template('index.html')

@app.route("/index.html")
def index():
    return render_template('index.html')


@app.route("/index.html")
def results():
    return render_template('index.html')

@app.route('/index.html', methods=['POST'])
def run_post():
    query_s = request.form['query_string']
    print(f'query={query_s}')
    gpt_answer, gpt_message_content = rag_gpt.answer_user_question(query_s)
    print(gpt_answer)


    lm_answer, lm_message_content = rag_lm.answer_user_question(query_s)
    print(lm_answer)
    return render_template('index.html',
                           gpt_answer=gpt_answer,
                           gpt_message_content = gpt_message_content,
                           lm_answer=lm_answer,
                           lm_message_content = lm_message_content
    )

if __name__ == "__main__":
    app.run(debug=True)