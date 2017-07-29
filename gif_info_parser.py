import sys
import re
import datetime
import dateutil.parser as dparser
import unidecode
from collections import defaultdict
from itertools import groupby
from nltk.corpus import stopwords

reload(sys)  
sys.setdefaultencoding('utf8')

def read_parsing_keywords(kfile):
    '''(Uglily) Parse custom file with keywords to use in the parsing step
       Create merged groups for later categorization
    '''
    keywords = defaultdict(lambda: defaultdict(list)) 
    with open(kfile,'r') as f:
        for line in f:
            if line.startswith('#') or line.startswith(" "):
                next
            else:
                words = line.rstrip().split(",")
                if words[0] == "ALTNAME":
                    words[2] = tuple([ w.lower() for w in words[2].split(":") ])
                    keywords[ words[0] ][ words[1].lower() ] = words[2]
                else:
                    # Store data as/is (L1 and L2)
                    keywords[ words[0] ][ words[1].lower() ].append(words[2].lower())
                    # Merge L2: categorize by L1 only
                    keywords[ "MERGED" ][ words[0] ].append(words[2].lower())
                    # Create Merged Category list
                    if words[0] in ["KITTEN","FACULTY","MOMCAT"]:
                        keywords["MERGED"]["CATEGORY"] = list(set(keywords["MERGED"]["CATEGORY"]+[words[1].lower()]))

    return(keywords)
                
def parse_date(string):
    ''' Apply fuzzy datetime.parser to strings. If a suitable date is not found,
    then 1900-01-01 is returned. Return value is a datetime object in date format'''
    try:
        dateString = dparser.parse(string,fuzzy=True)
        return (dateString.date())
    except ValueError:
        return datetime.date(2016,01,01)

def parse_giffer(string):
    ''' Apply ugly regex to extract the name of a putative giffer, assuming that 
    the string after a numerical value (end of the date string) is the giffer's name '''
    giffer_match = re.compile(r".*\d+_(.*)$")
    try:
        found = giffer_match.search(string)
        return(found.group(1))
    except:
        return("Unknown")
    
def search_word(w,d,default=None):
    ''' Search string to dictionary values and return the associated keywords
    If default is set, it returns the default value.
    If default is not set, it returns the original searched word'''
    word_list = [(k,v) for k,v in d.items()]
    for k,v in word_list:
        if w in v:
            return(k)
    if default is None:
        return(w)
    else:
        return(default)    

def categorize_words(wl,d, default="UNKNOWN"):
    ''' Categorize words according to input file categories'''
    categories = [search_word(w,d,default=default) for w in wl]
    CategorizedWords = defaultdict(list)
    for x in zip(categories,wl):
        CategorizedWords[x[0]].append(x[1])
    return(CategorizedWords)


def parse_category(w, categories, d):
    ''' Ugly function to parse category
    If the category is not present in the category list in the dictionary:
    1) Check if there are kittens associated. If so, add category from kittens
    2) Check if there are momcats associated. If so, add category from Momcat
    3) Check if there are faculty names or humans associated, add corresponding categories'''
    clss = w
    if clss in d["MERGED"]["CATEGORY"]:
        return(clss)
    elif clss not in d["MERGED"]["CATEGORY"] and len(categories["KITTEN"])>0:
        ## If class is incorrect, check if there are kitten names found
        return (','.join(list(set(search_word(w,d["KITTEN"]) for w in categories["KITTEN"]) )))
    elif clss not in d["MERGED"]["CATEGORY"] and len(categories["MOMCAT"])>0:
        ## If class is incorrect, check if there is a momcat name found
        return (','.join(list(set(search_word(w,d["MOMCAT"]) for w in categories["MOMCAT"]) )))
    elif clss not in d["MERGED"]["CATEGORY"] and len(categories["FACULTY"])>0:
        return("faculty")
    elif clss not in d["MERGED"]["CATEGORY"] and len(categories["HUMAN"])>0:
        return('humans')
    else:
        return("unknown")    

def print_categorization(x):
    ''' Join together keys and values'''
    k_val = ["KITTEN","MOMCAT","FACULTY","HUMAN","OTHER"]
    k_str = []
    for k in k_val:
        if k in x.keys():
            val = x[k]
        else:
            val = [""]
        k_str.append( ','.join(val) )

    l2 = ';'.join(['%s=%s' % t for t in zip(k_val, k_str)])
    return l2

def main():
    
    keywords = read_parsing_keywords("keywords.csv")
    
    # Print header    
    print '\t'.join(["#Category","Date","Giffer","URL","Parsed_Metadata"])

    for line in sys.stdin:
        
        # ------------------------ CLEAN UP STRING -------------------------
        # Split by gifURL file extension and following space because
        # someone thought putting spaces in the filename is Okay. But it's not.
        gifURL, gifMeta = re.split(r".gif\s+", line.rstrip())
        
        # 1st gsub: Replace special characters and spaces if present.
        # 2nd gsub: replace file extension in metadata
        gifMeta =  re.sub('[!@#$. ]', '', re.sub('.gif', '', gifMeta) )
        
        # --------------------------- PARSE INFO ---------------------------
        # Parse date. If missing, 2016/01/01 is assigned
        gifDate = parse_date(gifMeta)
        
        # Parse giffer's name
        gifGiffer = parse_giffer(gifMeta)
        
        # -------------------- PARSE AND CLASSIFY WORDS --------------------
        # Create a string without date and giffer
        gifMetaClean = re.sub('[-_]\d{4}.*$', '', gifMeta) 
        
        # Collapse possible _\d elements at the end of the string
        gifMetaClean = re.sub('_(\d{1})$', "\1", gifMetaClean)
        
        # Split words to process
        allWords = gifMetaClean.split("_")
        
        # Remove "stopwords" (common words) from the list.
        allWords = [word for word in allWords if word not in stopwords.words('english')]
        
        # Replace alternative words defined in the config file and
        # collapse consecutive repeated words
        allWordsReplaced = [search_word(word,keywords["ALTNAME"]) for word in allWords]
        allWordsReplaced = [x[0] for x in groupby(allWordsReplaced)]

        # Parse and classify relevant words: kittens, momcats, humans, other...
        categorizedWords = categorize_words(allWordsReplaced,keywords["MERGED"])
        
        # Define category 
        gifCategory = parse_category(allWordsReplaced[0],
                                        categorizedWords,
                                        keywords)
        
        categorizedWordsPrint = print_categorization(categorizedWords)
        
        print '\t'.join([gifCategory, str(gifDate), gifGiffer, gifURL, categorizedWordsPrint])
        
main()