import json, requests,time
from typing import Any, Dict, List, Optional
from tqdm import tqdm

def fetch_all_results(base_url: str, params: Dict[str, Any], headers: Dict[str, Any], timeout: int = 30, sleep_seconds: float = 0.2) -> List[Dict[str, Any]]:
	all_results: List[Dict[str, Any]] = []
	page = 1
	total_expected: Optional[int] = None

	while True:
		request_params = dict(params)
		request_params["page"] = page

		response = session.get(base_url, params=request_params, timeout=timeout)
		response.raise_for_status()

		data = response.json()
		header = data.get("header", {})
		results = data.get("results", [])

		if total_expected is None:
			total_expected = header.get("numFound")
		all_results.extend(results)

		if not results: break

		if total_expected is not None and len(all_results) >= total_expected: break

		page_size = header.get("pageSize", params.get("pageSize"))
		if page_size and len(results) < int(page_size): break
		page += 1
		time.sleep(sleep_seconds)
	return all_results

def get_coauthors(products, main_author = None, debug=False):
	ego_coauthors = dict()
	for work in products:
		authors = list()
		t = work['type']
		w_id = work['id']
		year = int(work['publicationDate'].split("-")[0]) if "publicationDate" in work and work['publicationDate'] is not None else 9999999
		work_authors = work['authors'] if isinstance(work['authors'], list) else json.loads(work['authors'])
		for author in work_authors:
			if "pid" in author and author['pid'] is not None: 
				if "orcid" in author['pid']['id']['scheme']:
					a = Author(author['fullName'], author['pid']['id']['value'])
					if not a in authors: authors.append(a)
		if main_author is not None and main_author in authors:
			for author in authors:
				if not author.orcid in ego_coauthors: ego_coauthors[author.orcid] = author
				ego_coauthors[author.orcid].works[w_id] = {'id': w_id, 'title': work['mainTitle'], 'type': work['type'], 'year': year}
		elif main_author is None:
			for author in authors:
				if not author.orcid in ego_coauthors: ego_coauthors[author.orcid] = author
				ego_coauthors[author.orcid].works[w_id] = {'id': w_id, 'title': work['mainTitle'], 'type': work['type'], 'year': year}
	return ego_coauthors

def retrieve_coauthors_works(ego_coauthors: Dict[str, Author], base_url: str, headers: Dict[str, Any]) -> List[Any]:
	all_works = {}
	for _, author in tqdm(ego_coauthors.items(), desc=f"Downloading products for {len(ego_coauthors)} authors"):
		auth_params = {
			"authorOrcid": author.orcid,
			"pageSize": 50,
			"sortBy": "publicationDate ASC",
		}
		res = fetch_all_results(base_url, auth_params, headers, show_timebar=False)
		for r in res:
			r_id = r['id']
			all_works[r_id] = r
	return all_works
