import nltk
import string
import numpy as np
import pandas as pd
from nltk.corpus import wordnet, stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.stem import WordNetLemmatizer
from nltk.util import ngrams
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from collections import Counter
from nltk import pos_tag, word_tokenize
from nltk.parse import CoreNLPParser
from pycorenlp import StanfordCoreNLP

nlp = StanfordCoreNLP('http://localhost:9000')
np.random.seed(0)

# Load the machine learning classifiers and count vectorizer
vectorizer = CountVectorizer(tokenizer=word_tokenize, stop_words=stopwords.words('english'))
df = pd.read_csv('chatgpt_training_data.csv')
X_train = vectorizer.fit_transform(df['text'])
y_train = df['is_chatgpt']
classifier1 = MultinomialNB()
classifier1.fit(X_train, y_train)
classifier2 = MultinomialNB()
classifier2.fit(X_train, y_train)
classifier3 = MultinomialNB()
classifier3.fit(X_train, y_train)

# Define the heuristics and their thresholds
heuristics = [('Capitalization', 10), ('Repetition', 10), ('Vocabulary', 10),
              ('Sentence Length', 10), ('Word Frequency', 10), ('Grammar Errors', 10),
              ('POS Tags', 10), ('Unusual Vocabulary', 10), ('Bayesian Probability', 50)]

def is_chatgpt(text):
    # Calculate the probabilities using the machine learning classifiers
    X_test = vectorizer.transform([text])
    p1 = classifier1.predict_proba(X_test)[0][1]
    p2 = classifier2.predict_proba(X_test)[0][1]
    p3 = classifier3.predict_proba(X_test)[0][1]

    # Calculate the scores for each of the heuristics
    words = word_tokenize(text.lower())
    word_counts = Counter(words)
    sentence_lengths = [len(word_tokenize(sent)) for sent in sent_tokenize(text)]
    avg_sent_length = np.mean(sentence_lengths)
    word_freq = [word_counts[w] for w in words]
    vocab_score = len(set(words)) / len(words)
    word_len_score = np.mean([len(w) for w in words])
    capitalization_score = sum([1 for w in words if w[0] in string.ascii_uppercase]) / len(words)
    repetition_score = len(words) / len(set(words))
    grammar_error_score = 1 - len(nltk.parse.util.extract_test_sentences([text])[0]) / len(sent_tokenize(text))
    pos_tag_score = sum([1 for _, t in pos_tag(words) if t.startswith('NN')]) / len(words)
    unusual_vocab_score = sum([1 for w in words if not wordnet.synsets(w)]) / len(words)

    # Calculate the Bayesian probability
    tokens = word_tokenize(text)
    pos_tags = nlp.annotate(text, properties={'annotators': 'pos', 'outputFormat': 'json'})['sentences'][0]['tokens']
    pos_tags = [token['pos'] for token in pos_tags]
    nouns = [tokens[i] for i, tag in enumerate(pos_tags) if tag.startswith('N')]
    verbs = [tokens[i] for i, tag in enumerate(pos_tags) if tag.startswith('V')]
    adjectives = [tokens[i] for i, tag in enumerate(pos_tags) if tag.startswith('J')]
    bayes_score = 1
    if len(nouns) > 0:
        bayes_score *= word_probability(nouns, 'noun')
    if len(verbs) > 0:
        bayes_score *= word_probability(verbs, 'verb')
    if len(adjectives) > 0:
        bayes_score *= word_probability(adjectives, 'adjective')

    # Calculate the final score as a weighted average of the scores from the heuristics and the Bayesian probability
    heuristic_scores = [capitalization_score, repetition_score, vocab_score, word_len_score, np.mean(word_freq),
                        grammar_error_score, pos_tag_score, unusual_vocab_score, bayes_score]
    weights = [p1, p2, p3]
    score = np.average(heuristic_scores, weights=weights)

    # Determine if the text was generated by ChatGPT based on the score and threshold
    if score > 0.5:
        return f'The text was generated by ChatGPT with a probability of {score * 100:.2f}%'
    else:
        return f'The text was not generated by ChatGPT with a probability of {(1 - score) * 100:.2f}%'

def word_probability(words, pos):
    """
    Calculates the probability of a set of words given their part-of-speech tag using a Bayesian network.
    """
    # Load the conditional probability tables
    cpd_noun = pd.read_csv(f'{pos}_probability_nouns.csv', index_col=0)
    cpd_verb = pd.read_csv(f'{pos}_probability_verbs.csv', index_col=0)
    cpd_adj = pd.read_csv(f'{pos}_probability_adjectives.csv', index_col=0)

    # Calculate the joint probability of the words given their part-of-speech tag
    if pos == 'noun':
        cpd = cpd_noun
    elif pos == 'verb':
        cpd = cpd_verb
    elif pos == 'adjective':
        cpd = cpd_adj
    else:
        return 1
    prob = 1
    for w in words:
        if w in cpd.index:
            prob *= cpd.loc[w]['Probability']
        else:
            prob *= cpd.loc['<UNK>']['Probability']
    return prob
