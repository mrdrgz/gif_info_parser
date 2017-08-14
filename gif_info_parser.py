import sys
import re
import datetime
import dateutil.parser as dparser
import unidecode
from collections import defaultdict
from itertools import groupby
import requests
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
                
def parse_date(string, default_date=datetime.date(2016,01,01)):
    ''' Apply fuzzy datetime.parser to strings. If a suitable date is not found,
    then the default date is returned. Return value is a datetime object in date format'''
   
    # Fix dates with _ between numbers (in all kinds of horrible combinations)
    string_fixed = re.sub(r"(\d{2,4})_(\d+)_(\d+)", r"\1-\2-\3", string)
    string_fixed = re.sub("_(17)-(\d+)-(\d+)", r"_2017-\2-\3", string_fixed)
    string_fixed = re.sub("-(\d{2})_(\d{2})", r"\1-\2", string_fixed)
    string_fixed = re.sub("_(\d{4})_(\d{2})", r"\1-\2", string_fixed)
    
    try:
        dateString = dparser.parse(string_fixed,fuzzy=True).date()
        if dateString > datetime.datetime(2015,1,1).date() and dateString < datetime.datetime.now().date():
            return (dateString)
        else:
            return default_date
    except ValueError:
        match_full_date    = re.search(r'(\d{2,4}-\d{2}-\d{2})', string)
        match_partial_date = re.search(r'(\d{2,4}-\d{2})', string)
        if match_full_date is not None:
            return(match_full_date.group(0))
        elif match_partial_date is not None:
            dateString = "{}-00".format(match_partial_date.group(0))
            return(dateString)
        else:
            return "1970-01-01"

def parse_giffer(string):
    ''' Apply ugly regex to extract the name of a putative giffer, assuming that 
    the string after a numerical value (end of the date string) is the giffer's name '''
    giffer_match = re.compile(r".*\d+_(.*)$")
    try:
        found = giffer_match.search(string)
        giffer_name = found.group(1)
        if (re.search('[a-zA-Z]', giffer_name)):
            return(giffer_name)
        else:
            return("Unknown")
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
    ''' Categorize words according to the defined input file categories'''
    categories = [search_word(w,d,default=default) for w in wl]
    CategorizedWords = defaultdict(list)
    for x in zip(categories,wl):
        CategorizedWords[x[0]].append(x[1])
    return(CategorizedWords)

def parse_category(cat, categories, d):
    ''' Ugly function to parse category
    If the category is not present in the category list in the dictionary:
    1) Check if there are kittens associated. If so, add category from kittens
    2) Check if there are momcats associated. If so, add category from Momcat
    3) Check if there are faculty names or humans associated, add corresponding categories'''
    if cat in d["MERGED"]["CATEGORY"]:
        return(cat)
    elif cat not in d["MERGED"]["CATEGORY"] and len(categories["KITTEN"])>0:
        ## If class is incorrect, check if there are kitten names found
        return (','.join(list(set(search_word(w,d["KITTEN"]) for w in categories["KITTEN"]) )))
    elif cat not in d["MERGED"]["CATEGORY"] and len(categories["MOMCAT"])>0:
        ## If class is incorrect, check if there is a momcat name found
        return (','.join(list(set(search_word(w,d["MOMCAT"]) for w in categories["MOMCAT"]) )))
    elif cat not in d["MERGED"]["CATEGORY"] and len(categories["FACULTY"])>0:
        return("faculty")
    elif cat not in d["MERGED"]["CATEGORY"] and len(categories["HUMAN"])>0:
        return('humans')
    else:
        return("unknown")    

def print_categorization(x,k_val=["KITTEN","MOMCAT","FACULTY","HUMAN","OTHER"]):
    ''' Join together keys and values'''
    k_str = []
    for k in k_val:
        if k in x.keys():
            val = x[k]
        else:
            val = [""]
        k_str.append( ','.join(val) )

    l2print = ';'.join(['%s=%s' % t for t in zip(k_val, k_str)])
    return l2print

def get_all_gifs():
    '''Request all gifs in JSON format'''
    api_url = "http://kitten.ga/tags/?text="
    response = requests.get(api_url)
    data = response.json()
    return(data)


def main():
    
    keywords = read_parsing_keywords("keywords.csv")
    
    # Print header    
    print '\t'.join(["Category","Date","Giffer","URL","Parsed_Metadata", "Cleaned_Metadata", "Original_Metadata"])
    
    allGifs = get_all_gifs()
    
    
    for gif in allGifs:
        # ------------------------ CLEAN UP STRING -------------------------
        # Split by gifURL file extension and following space because
        # someone thought putting spaces in the filename is Okay. But it's not.
        gifURL = "http://kitten.ga/gifs/{}.gif".format(gif['id'])
        gifMeta = gif['name']
        
        # Fix smol non-unicode problem... by deleting those evil characters
        gifMeta = gifMeta.encode('ascii', 'ignore')
        
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
        gifMetaClean = re.sub('[-_]\d{2,4}.*$', '', gifMeta) 
        
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
        
        print '\t'.join([gifCategory, str(gifDate), gifGiffer, gifURL, categorizedWordsPrint, gifMetaClean, gifMeta])
        
main()