# research-group-detection

1) **research_groups_detection.py** --> contains all the classes and methods needed to compute communities and research groups
2) **download_from_openaire_api.py** --> it contains the methods to fetch the results from the OpenAIRE graph API given an ORCID identifier
3) **research_group_main.py** --> contains three methods:
   - _get_research_products_ that retrieve and return as output the research products from the OpenAIRE graph API
   - _get_research_groups_ given in input the research products, launch the entire pipeline in order to detect the research groups. It returns them, a dictionary mapping authors' ORCIDs with their names, and the research products' details for the works involved in the research groups
   - _main_ a function that, given an ORCID identifier, runs the above functions and saves the JSON data   
 
