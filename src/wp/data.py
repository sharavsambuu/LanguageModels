
"""
Data module - wraps all data and handles processing.

Usage:
data = Data('animals')
data.prepare()
s = data.text('train')
sentences = data.sentences('train')
tokens = data.tokens('test')
"""

import sys
import os.path
import random
import glob
import re
from pprint import pprint
from collections import defaultdict
import codecs

import numpy as np
import pandas as pd
import nltk
from nltk import tokenize
from textstat.textstat import textstat

import vocab
import util
from benchmark import benchmark


class Data(object):
    """
    Wrapper around all data files, with splitter and tokenizers.
    """

    def __init__(self, name):
        """
        Create a data object - contains little to no state - most is in predefined files.
        """
        self.name = name
        escape = '../../' # escape from the Experiment subfolder, where this is called from
        dataset_folder = escape + 'data/' + name + '/'
        model_folder = escape + 'models/' + name + '/'
        self.model_folder   = model_folder
        self.raw_folder     = dataset_folder + '1-raw/'
        self.cleaned_folder = dataset_folder + '2-cleaned/'
        self.merged_folder  = dataset_folder + '3-merged/'
        self.split_folder   = dataset_folder + '4-split/'
        self.raw_files      = self.raw_folder + '*.txt'
        self.cleaned_files  = self.cleaned_folder + '*.txt'
        self.merged_file    = self.merged_folder + 'all.txt'
        self.splitparts = ('train','validate','test')
        self.source_files = {
            'raw': self.raw_files,
            'cleaned': self.cleaned_files,
            'merged': self.merged_file,
            'train': self.split_folder + 'all-train.txt',
            'validate': self.split_folder + 'all-validate.txt',
            'test': self.split_folder + 'all-test.txt',
        }
        self.encodings = ['utf8', 'cp1252', 'latin1']

    def prepare(self, ptrain=0.8, pvalidate=0.0, ptest=0.2): # same defaults are also specified in .split
        """
        Clean, merge, and split raw data files into train, validate, test sets.
        """
        print('Prepare dataset:', self.name)
        with benchmark("Dataset prepared"):
            self.clean()
            self.merge()
            self.split(ptrain, pvalidate, ptest)
        print()

    def clean(self):
        """
        Clean raw files - remove Gutenberg header/footers, table of contents, nonascii chars.
        """
        print('Clean raw files... ',end='')
        util.mkdir(self.cleaned_folder)
        for infile in glob.glob(self.raw_files):
            _, filetitle = os.path.split(infile)
            outfile = self.cleaned_folder + filetitle
            if not os.path.isfile(outfile):
                # print('Cleaning %s to %s' % (infile, filetitle))
                # try:
                # for encoding in self.encodings:
                # with open(infile, 'r') as f_in:
                # with open(infile, 'r', encoding=encoding, errors='replace') as f_in:
                encoding = 'utf8'
                # with codecs.open(infile, 'r', encoding=encoding, errors='replace') as f_in:
                with codecs.open(infile, 'r', encoding=encoding, errors='ignore') as f_in:
                    s = f_in.read()
                    s = s.replace('\r\n','\n') # dos2unix
                    s = self.clean_header_footer(s)
                    s = self.clean_table_of_contents(s)
                    # strip out any non-ascii characters - nltk complains otherwise
                    #. need better way to handle this - eg convert to miserables, not misrables
                    #. use decode?
                    # s = re.sub(r'[^\x00-\x7f]',r'', s)
                    # with open(outfile, 'wb') as f_out:
                    with open(outfile, 'w') as f_out:
                        f_out.write(s)
                # except:
                    # pass
        print("done.")

    def clean_header_footer(self, s):
        """
        Remove the Gutenberg header and footer/license from the given string.
        """
        s = util.remove_text(r"\*\*\*[ ]*START OF.*\*\*\*", s, 0)
        s = util.remove_text(r"\*\*\*[ ]*END.*\*\*\*", s, -1)
        return s

    def clean_table_of_contents(self, s):
        """
        Remove table of contents from specific texts.
        """
        s = util.remove_text(r"LENOX, January 27, 1851.", s, 0) # house of seven gables
        s = util.remove_text(r"List of Illustrations", s, 0) # les miserables
        s = util.remove_text(r"\[Sidenote\: _Down the Rabbit-Hole_\]", s, 0) # alice
        s = util.remove_text(r"PART ONE--The Old Buccaneer", s, 0) # treasure island
        s = util.remove_text(r"CANON ALBERIC'S SCRAP-BOOK", s, 0) # mrjames1905
        s = util.remove_text(r"I. THE RIVER BANK", s, 0) # windinwillows
        return s

    def merge(self):
        """
        Merge the cleaned files into one file if not done yet.
        """
        # print('Merge cleaned files...')
        print('Merge cleaned files... ', end='')
        util.mkdir(self.merged_folder)
        if not os.path.isfile(self.merged_file):
            # with open(self.merged_file, 'wb') as f_all:
            with open(self.merged_file, 'w') as f_all:
                for filename in glob.glob(self.cleaned_files):
                    # print('Adding', filename)
                    # with open(filename, 'rb') as f:
                    with open(filename, 'r') as f:
                        s = f.read()
                        f_all.write(s)
        print('done.')
        # print()

    def split(self, ptrain=0.8, pvalidate=0.0, ptest=0.2): # same defaults are also specified in .prepare
        """
        Split a textfile on sentences into train, validate, and test files.
        Will put resulting files in specified output folder with -train.txt etc appended.
        ptrain, pvalidate, ptest: proportion of original file to put into respective output files
        Note: we need to split on sentences, not lines, otherwise would wind up with
        artificial word tuples.
        """
        assert abs(ptrain + pvalidate + ptest - 1) < 1e-6 # must add to 1.0
        # print('Split merged file...')
        print('Split merged file... ', end='')
        # initialize
        util.mkdir(self.split_folder)
        proportions = (ptrain, pvalidate, ptest)
        filetitle = os.path.basename(self.merged_file)[:-4] # eg 'all'
        output_filenames = [self.split_folder + '/' + filetitle + '-' + splitpart
                            + '.txt' for splitpart in self.splitparts] # eg 'all-train.txt'
        # do the output files already exist?
        allexist = True
        for output_filename in output_filenames:
            if not os.path.isfile(output_filename):
                allexist = False
                break
        if not allexist:
            try:
                os.mkdir(self.split_folder)
            except:
                pass
            output_files = []
            # open output files for writing
            for output_filename in output_filenames:
                # f = open(output_filename, 'wb')
                f = open(output_filename, 'w')
                output_files.append(f)
            # parse merged file into sentences
            # print('Splitting merged file into sentences')
            sentences = self.sentences('merged')
            # walk over sentences, outputting to the different output files
            # print('Distributing sentences over output files')
            for sentence in sentences:
                f = self._get_next_file(output_files, proportions)
                f.write(sentence)
                f.write('\n\n')
            # close all files
            for f in output_files:
                f.close()
        print('done.')
        # print()

    def _get_next_file(self, output_files, proportions):
        """
        Get next output file to write to based on specified proportions.
        This is used by split method to split a file into train, validate, test files.
        output_files - a list of file handles
        proportions  - a list of floating point numbers that add up to one,
          representing the proportion of text to be sent to each file.
        Returns a file handle.
        """
        # determine which file to write to by comparing the current file size
        # proportions against the given proportions, writing to the first one
        # found with a lower proportion than desired.
        nchars = [f.tell() for f in output_files] # file sizes
        ntotal = sum(nchars)
        if ntotal==0:
            return output_files[0] # start with first file
        pcurrent = [n/ntotal for n in nchars] # file proportions
        # find file that needs more data
        for i in range(len(output_files)):
            if pcurrent[i] < proportions[i]:
                return output_files[i] # return the first under-appreciated file
        return output_files[0] # otherwise just return the first file

    def analyze(self):
        """
        Gather some statistics on the datafiles.
        """
        rows = []
        cols = ['Text','Chars','Words','Sentences', 'Chars / Word', 'Words / Sentence', 'Unique Words', 'Unique Rate', 'Grade Level']
        for filepath in glob.glob(self.cleaned_files):
            # with open(filepath, 'rb') as f:
            with open(filepath, 'r') as f:
                s = f.read()
                s = s.lower()
                words = s.split(' ')
                filetitle = util.filetitle(filepath)
                sentences = tokenize.sent_tokenize(s)
                nchars = len(s)
                nwords = len(words)
                nsentences = len(sentences)
                ncharsword = round(nchars/nwords,1)
                nwordssentence = round(nwords/nsentences,1)
                nuniquewords = len(set(words))
                uniquerate = nuniquewords / nwords
                grade_level = int(round(textstat.coleman_liau_index(s)))
                row = [filetitle, nchars, nwords, nsentences, ncharsword, nwordssentence, nuniquewords, uniquerate, grade_level]
                rows.append(row)
        nchars = sum([row[1] for row in rows])
        nwords = sum([row[2] for row in rows])
        row = ['Totals',nchars, nwords, '','','','','','']
        rows.append(row)
        df = pd.DataFrame(rows, columns=cols)
        df = df.drop('Chars',axis=1) # not enough space...
        df = df.drop('Sentences',axis=1)
        df = df.drop('Unique Rate',axis=1)
        return df

    def histogram(self, nsentences=100, nwordsmax=100):
        """
        Get histogram data of sentence length for the different cleaned texts.
        nsentences - limit to sample of this many sentences, for speed (eg lesmis has 35k sentences).
        nwordsmax  - set wordcounts greater than this to NaN (to ignore giant outlier sentences).
        """
        lengths = []
        filetitles = []
        for filepath in glob.glob(self.cleaned_files):
            # with open(filepath, 'rb') as f:
            with open(filepath, 'r') as f:
                s = f.read()
                sentences = tokenize.sent_tokenize(s)
                sentences = random.sample(sentences, nsentences) # sample sentences
                nwords = [len(sentence.split()) for sentence in sentences]
                lengths.append(nwords)
                filetitle = util.filetitle(filepath)
                filetitles.append(filetitle)
        df = pd.DataFrame(lengths, index=filetitles)
        df = df.applymap(lambda x: x if x < nwordsmax else np.NaN)
        return df

    def text(self, source='merged', amount=1.0):
        """
        Return contents of a data source up to given amount (percentage or nchars).
        """
        #. use generators
        filename = self.source_files[source]
        ntotal = os.path.getsize(filename)
        # if amount <= 1.0, treat it as a percentage, else nchars
        if amount <= 1.0:
            nchars = int(ntotal * amount)
        else:
            nchars = int(amount)
        # with open(filename, 'rb') as f:
        with open(filename, 'r') as f:
            s = f.read(nchars)
        return s

    def sentences(self, source='merged', amount=1.0):
        """
        Parse a data source into sentences and return in a list.
        """
        #. use generators
        s = self.text(source, amount)
        s = s.replace('\r\n',' ')
        s = s.replace('\n',' ')
        sentences = tokenize.sent_tokenize(s)
        return sentences

    def tokens(self, source='merged', amount=1.0):
        """
        Parse a data source into tokens and return in a list.
        """
        #. trim vocab here? ie use UNKNOWN where needed?
        #. use generators
        with benchmark("Get tokens from data source"):
            sentences = self.sentences(source, amount)
            tokens = []
            for sentence in sentences:
                sentence = sentence.lower() # reduces vocab space
                words = tokenize.word_tokenize(sentence)
                tokens.extend(words)
                tokens.append('END') # add an END token to every sentence #. magic
        return tokens

    def get_vocab(self, train_amount, nvocab):
        """
        Get a vocabulary object containing the top nvocab words from the training data.
        """
        #. would like this to memoize these if not too much memory, or else pass in tokens and calc them in Experiment class
        tokens = self.tokens('train', train_amount) # eg ['a','b','.','END']
        vocab = vocab.Vocab(tokens, nvocab)
        return vocab

    def __str__(self):
        """
        Return text representation of data object.
        """
        s = "Dataset %s" % self.name
        # self.source_files
        return s

    def readability(self):
        """
        Return grade school readability level of the text, using consensus of several tests.
        """
        s = self.text('merged')
        # grade_level = textstat.text_standard(s)
        # grade_level = textstat.smog_index(s)
        # grade_level = textstat.gunning_fog(s)
        grade_level = textstat.coleman_liau_index(s)
        grade_level = round(grade_level,1)
        return grade_level

    # def tuples(self, source, ntokens_per_tuple, nchars=None):
    #     """
    #     Parse a data source into tokens up to nchars and return as tuples.
    #     """
    #     #. use generators!
    #     tokens = self.tokens(source)
    #     tokenlists = [tokens[i:] for i in range(ntokens_per_tuple)]
    #     tuples = zip(*tokenlists) # eg [['the','dog'], ['dog','barked'], ...]
    #     return tuples


# Split a textfile by sentences into train, validate, test files,
# based on specified proportions.
# Usage:
# >>> import split
# >>> split.split('data/raw/all.txt', 'data/split', 0.8, 0.1, 0.1)
# or
# $ python src/split.py --ptrain 0.8 --pvalidate 0.1 --ptest 0.1 data/raw/all.txt data/split
# if __name__ == '__main__':
#     # command line handler
#     # see https://pypi.python.org/pypi/argh
#     import argh
#     argh.dispatch_command(split)

if __name__ == '__main__':

    # from tabulate import tabulate

    # # abcd
    # data = Data('abcd')
    # # build the abcd dataset with same test set as train set (data is duplicated in raw text file)
    # # data.prepare(ptrain=0.5, pvalidate=0, ptest=0.5)
    # print(util.table(data.analyze()))
    # | Text   |   Words | Chars / Word   | Words / Sentence   | Unique Words   | Grade Level   |
    # |--------+---------+----------------+--------------------+----------------+---------------|
    # | text   |      10 | 2.0            | 5.0                | 6              | -15           |

    # # alphabet
    # data = Data('alphabet')
    # # build the alphabet dataset with same test set as train set (data is duplicated in raw text file)
    # # data.prepare(ptrain=0.5, pvalidate=0, ptest=0.5)

    # # alice
    # data = Data('alice1')
    # # data.prepare(ptrain=0.9, pvalidate=0, ptest=0.1)
    # print(util.table(data.analyze()))
    # | Text   |   Words | Chars / Word   | Words / Sentence   | Unique Words   | Grade Level   |
    # |--------+---------+----------------+--------------------+----------------+---------------|
    # | text   |    2044 | 5.6            | 23.2               | 843            | 8             |


    # # animals
    # data = Data('animals')
    # print(util.table(data.analyze()))
    # print(data.readability()) # grade level
    # print(data.text())
    # print(data.sentences())
    # print(data.tokens())
    # # print(data.text('train'))
    # # print(data.text('train',0.5))
    # # print(data.text('train',20))
    # # print(data)
    # # print()


    # data = Data('gutenbergs')
    # with benchmark("prepare"):
        # data.prepare(ptrain=0.9, pvalidate=0.05, ptest=0.05) # 6 secs
    # with benchmark("analyze"):
        # print(util.table(data.analyze())) # 25 secs
    # with benchmark("tokens"):
        # tokens = data.tokens() # 18 secs

    # # get histogram of sentence lengths - currently plotted in the notebook
    # data = Data('gutenbergs')
    # df = data.histogram(100, 100)
    # print(df)
    # import matplotlib.pyplot as plt
    # plt.figure(figsize=(12,7))
    # # plt.hist(lengths, range=(1,40), bins=40, stacked=True, label=filetitles, alpha=0.5, weights=weights)
    # plt.hist(lengths, range=(2,30), bins=28, stacked=True, label=filetitles, alpha=0.5, weights=weights)
    # plt.legend(loc=(1.1,0.5))
    # plt.grid()
    # plt.subplots_adjust(left=0.01,right=0.5)
    # plt.show()


    # s = "header\n*** START OF TEXT ***\n contents \n*** END OF TEXT ***\n license"
    # s = data.clean_header_footer(s)
    # print(s)
    # tokens = data.tokens('train', 300)
    # print('train:',tokens)
    # print()
    # tokens = data.tokens('test', 300)
    # print('test:',tokens)
    # print()
    # sentences = data.sentences('train', 300)
    # print('train sentences:',sentences)
    # print()

    # s = 'The dog barked. The cat slept.'
    # nvocab = 3
    # vocab = Vocab(s.split(), nvocab)
    # print(vocab)
    # print(vocab.index_to_word)
    # print(vocab.word_to_index)

    # tokenized_sentences = data.tokenized_sentences('train', 300)
    # print('train:',tokenized_sentences)
    # print()
    # indexed_sentences = data.indexed_sentences('train', 300)
    # print('train:',indexed_sentences)
    # print()


    pass
