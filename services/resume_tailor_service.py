import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

stop_words = set(stopwords.words('english'))

def extract_keywords(text):
    tokens = word_tokenize(text.lower())
    keywords = []
    custom_stops = {"need", "use", "work", "role", "experience", 
                "skills", "ability", "knowledge", "good", "strong"}
    for word in tokens:
        if word.isalpha():           # only real words, no punctuation
            if word not in stop_words and word not in custom_stops:  # remove stop words
                keywords.append(word)
    return set(keywords) 


def calculate_match(resume_text, job_description):
    resume_extract = extract_keywords(resume_text)
    job_extract = extract_keywords(job_description)
    matchh = []
    missing = []
    for ex in resume_extract:
        if ex in job_extract:
            matchh.append(ex)
    for ex in job_extract:
        if ex not in resume_extract:
            missing.append(ex)
    #total_len = len(resume_extract) + len(job_extract)
    mat_len = len(matchh)
    mat_per = mat_len / len(job_extract) * 100
    return mat_per,matchh,missing



def term_freq(text):
    t_wrds = len(text)
    wrd_count = {}
    for word in text:
        if word in wrd_count:
            wrd_count[word] += 1  # already seen, add 1
        else:
            wrd_count[word] = 1
    tf={}
    for word in wrd_count:
        tf[word] = wrd_count[word] / t_wrds

    return tf

words = ["python", "sql", "python", "data", "python"]
print(term_freq(words))