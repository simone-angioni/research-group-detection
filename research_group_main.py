from .research_groups_detection import *
from .download_from_openaire_api import *


def build_network_from_orcid(orcid, progress_callback: Optional[Callable] = None):
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
    
    all_works = retrieve_coauthors_works(ego_coauthors, BASE_URL, HEADERS)
    enrich_works_for_coauthors(all_works, ego_coauthors)

    coauthorships = compute_coauthorships(all_works, ego_coauthors)
    network = build_network(coauthorships)
    finder = RecursiveCommunitiesFinder(network, leidenalg.ModularityVertexPartition)
    ego = ego_coauthors[orcid]
    communities = finder.extract(ego, 1)

    total_works_by_year = {}
    for year, works_in_year in ego.get_works_sorted_by_year().items():
        total_works_by_year[year] = len(works_in_year)

    threshold = 0.3

    temporal_research_groups, authors, output_works = compute_temporal_research_groups(communities, threshold)

    members = get_members(temporal_research_groups)
    members = {}
    for year, values in years.items():
        members[year] = values['research-group']
    
    coauthors_per_year = get_coauthors_per_year(coauthorships, ego)
    research_groups = assemble_research_groups(members, communities, ego, coauthors_per_year)

    graph = {'research-groups-overview':[{'id': i, 'start': g['start'], 'end': g['end'], 'research-group': [authors[m] for m in g['members']]}for i, g in enumerate(research_groups, start=1)],
		 'years': years}

    return graph, authors, output_works
