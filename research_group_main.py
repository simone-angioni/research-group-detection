from .research_groups_detection import *
from .download_from_openaire_api import *

def get_research_products(orcid):
    BASE_URL = "https://api.openaire.eu/graph/v2/researchProducts"

    PARAMS = {
        "authorOrcid": orcid,
        "pageSize": 50,
        "sortBy": "publicationDate ASC",
    }

    HEADERS = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; OpenAIREFetcher/1.0)",
    }

    products = fetch_all_results(
        BASE_URL, PARAMS, HEADERS,
        progress_callback=progress_callback,
        label=f"Main author ({orcid})",
    )

    ego_coauthors = get_coauthors(products)
    
    research_products = retrieve_coauthors_works(ego_coauthors, BASE_URL, HEADERS)
    enrich_works_for_coauthors(research_products, ego_coauthors)
    return research_products

def get_research_groups(research_products):
    coauthorships = compute_coauthorships(research_products, ego_coauthors)
    network = build_network(coauthorships)
    finder = RecursiveCommunitiesFinder(network, leidenalg.ModularityVertexPartition)
    ego = ego_coauthors[orcid]
    communities = finder.extract(ego, 1)

    total_works_by_year = {}
    for year, works_in_year in ego.get_works_sorted_by_year().items():
        total_works_by_year[year] = len(works_in_year)

    threshold = 0.3

    temporal_research_groups, authors_mapping, research_products_detailed = compute_temporal_research_groups(communities, threshold)

    members = get_members(temporal_research_groups)
    
    coauthors_per_year = get_coauthors_per_year(coauthorships, ego)
    research_groups = assemble_research_groups(members, communities, ego, coauthors_per_year)

    graph = {'research-groups-overview':[{'id': i, 'start': g['start'], 'end': g['end'], 'research-group': [authors[m] for m in g['members']]}for i, g in enumerate(research_groups, start=1)],
		 'years': temporal_research_groups}

    return graph, authors, research_products_detailed

def main(orcid):
    research_products = get_research_products(orcid)
    graph, authors_mapping, research_products_detailed = get_research_groups(research_products)
    with open(f"{orcid}-rg-network.json", "w") as f:
        json.dump(graph)
    with open(f"{orcid}-rg-network-author-names.json", "w") as f:
        json.dump(authors_mapping)
    with open(f"{orcid}-rg-network-products-details.json", "w") as f:
        json.dump(research_products_detailed)