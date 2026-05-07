from __future__ import annotations

import csv, io, json, leidenalg

from collections import Counter, defaultdict
from collections.abc import MutableSequence
from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple
from tqdm import tqdm
import igraph as ig

### ---- CLASSES ----

@dataclass(frozen=True)
class Author:
	name: str = field(repr=False)
	orcid: str
	works: Dict[str, Any] = field(default_factory=dict, init=False)

	def is_main(self, orcid: str) -> bool:
		return self.orcid == orcid

	def matches(self, other: "Author | str") -> bool:  
		if isinstance(other, Author):
			return self.orcid == other.orcid
		if isinstance(other, str):
			return self.orcid == other
		return False

	def as_dict(self) -> Dict[str, str]:
		return {"name": self.name, "orcid": self.orcid}

	def get_works_sorted_by_year(self) -> Dict[int, List[Dict[Any]]]:
		years = {}
		items = dict(sorted(self.works.items(), key=lambda x: x[1]['year']))
		for _, work in items.items():
			year = work['year']
			if not year in years: years[year] = []
			years[year].append(work)
		return years

	def __str__(self) -> str:
		return f"{self.name}: {self.orcid}"

	def __eq__(self, other: object) -> bool:  
		if isinstance(other, Author):
			return self.orcid == other.orcid
		if isinstance(other, str):
			return self.orcid == other
		
		return self.orcid == other.orcid
		

	def __hash__(self) -> int:
		return hash(self.orcid)

@dataclass
class Edge:
	source: Author
	target: Author
	date: datetime
	work: Dict[str, Any]

	@cached_property
	def year(self) -> int:
		return self.date.year

	def as_tuple(self):
		return (self.source, self.target, self.year)

	def as_couple(self):
		return (self.source, self.target)

	def as_dict(self):
		return {
			"source": self.source.as_dict(),
			"target": self.target.as_dict(),
			"year": self.year,
			"work": self.work,
		}

	def __repr__(self) -> str:
		return f"({self.source},{self.target},{self.year})"

@dataclass
class EdgeList(MutableSequence):
	edges: List[Edge] = field(default_factory=list, init=False)

	def append(self, value: Edge) -> None:
		self._validate(value)
		self.edges.append(value)

	def filter_by_year(self, year: int) -> List[Edge]:
		return [edge for edge in self.edges if edge.year == year]

	def sort_by(self, field_name: str, reverse: bool = False) -> None:
		self.edges.sort(key=lambda e: getattr(e, field_name), reverse=reverse)

	def sorted(self, field_name: str, reverse: bool = False) -> List[Edge]:
		return list(sorted(self.edges, key=lambda e: getattr(e, field_name), reverse=reverse))

	def insert(self, index: int, object: Edge) -> None:
		self._validate(object)
		self.edges.insert(index, object)

	def _validate(self, value) -> None:
		if not isinstance(value, Edge):
			raise TypeError("Only Edge instances can be added to EdgeList")

	def __len__(self) -> int:
		return len(self.edges)

	def __getitem__(self, index) -> Edge:
		return self.edges[index]

	def __setitem__(self, index, value: Edge) -> None:
		self._validate(value)
		self.edges[index] = value

	def __delitem__(self, index) -> None:
		del self.edges[index]

	def __iter__(self) -> Iterator[Edge]:
		return iter(self.edges)

@dataclass
class CoAuthorship:  
	source: Author
	target: Author
	_edges: EdgeList = field(default_factory=EdgeList, repr=False)

	def add_edge(self, edge: Edge) -> None:
		self._edges.append(edge)

	@property
	def edges(self) -> EdgeList:
		return self._edges

	@property
	def weight(self) -> int:
		return len(self._edges)

	@property
	def authors(self) -> Tuple[Author, Author]:
		return (self.source, self.target)

	def key(self) -> Tuple[str, str]:  
		return tuple(sorted((self.source.orcid, self.target.orcid)))

	def as_compact_row(self) -> Dict[str, Any]:  
		return {
			"source": self.source.orcid,
			"target": self.target.orcid,
			"weight": self.weight,
		}

	def rows_compact_by_year(self) -> List[Dict[str, Any]]:  
		aggregate: Dict[int, int] = defaultdict(int)
		for edge in self._edges:
			aggregate[edge.year] += 1
		return [
			{
				"year": year,
				"source": self.source.orcid,
				"target": self.target.orcid,
				"weight": weight,
			}
			for year, weight in sorted(aggregate.items())
		]

	def rows_extended_by_year(self) -> List[Dict[str, Any]]:  
		aggregate: Dict[int, Dict[str, Any]] = {}
		all_types: set[str] = set()
		for edge in self._edges:
			year = edge.year
			if year not in aggregate:
				aggregate[year] = {"year": year, "weight": 0, "type_counts": Counter()}
			aggregate[year]["weight"] += 1
			work_type = (edge.work or {}).get("type") or "unknown"
			aggregate[year]["type_counts"][work_type] += 1
			all_types.add(work_type)

		rows: List[Dict[str, Any]] = []
		ordered_types = sorted(all_types)
		for year in sorted(aggregate):
			row = {
				"year": year,
				"source": self.source.orcid,
				"target": self.target.orcid,
				"weight": aggregate[year]["weight"],
			}
			for work_type in ordered_types:
				row[work_type] = aggregate[year]["type_counts"].get(work_type, 0)
			rows.append(row)
		return rows

@dataclass
class CoAuthorshipList(MutableSequence):
	items: List[CoAuthorship] = field(default_factory=list, init=False)

	def append(self, value: CoAuthorship) -> None:
		self._validate(value)
		self.items.append(value)

	def insert(self, index: int, object: CoAuthorship) -> None:
		self._validate(object)
		self.items.insert(index, object)

	def _validate(self, value) -> None:
		if not isinstance(value, CoAuthorship):
			raise TypeError("Only CoAuthorship instances can be added to CoAuthorshipList")

	def __len__(self) -> int:
		return len(self.items)

	def __getitem__(self, index) -> CoAuthorship:
		return self.items[index]

	def __setitem__(self, index, value: CoAuthorship) -> None:
		self._validate(value)
		self.items[index] = value

	def __delitem__(self, index) -> None:
		del self.items[index]

	def __iter__(self) -> Iterator[CoAuthorship]:
		return iter(self.items)

@dataclass
class Community:
	id: str
	graph: Optional[ig.Graph]
	_authors: set[str] = field(default_factory=set, repr=False, init=False)
	_coauthorships: CoAuthorshipList = field(default_factory=CoAuthorshipList, repr=False)

	def add_author(self, author: Author) -> None:
		self._authors.add(author.orcid)

	def add_coauthorship(self, coauthorship: CoAuthorship) -> None: 
		self._coauthorships.append(coauthorship)

	@property
	def authors(self) -> set[str]:
		return set(self._authors)

	@property
	def coauthorships(self) -> CoAuthorshipList:
		return self._coauthorships

	@property
	def edges(self) -> EdgeList:
		combined = EdgeList()
		for coauthorship in self._coauthorships:
			for edge in coauthorship.edges:
				combined.append(edge)
		return combined

	def __contains__(self, author: object) -> bool:
		if isinstance(author, str):
			return author in self._authors
		if isinstance(author, Author):
			return author.orcid in self._authors
		raise TypeError(f"{author} should be a string or Author")

	def __len__(self) -> int:
		return len(self._authors)

@dataclass
class Communities:
	_data: Dict[int, Community] = field(default_factory=dict, init=False, repr=False)
	_author_index: Dict[str, int] = field(default_factory=dict, init=False, repr=False)

	def get(self, community_id: int, graph: Optional[ig.Graph] = None) -> Community:
		if community_id not in self._data:
			self._data[community_id] = Community(id=str(community_id), graph=graph)
		elif graph is not None and self._data[community_id].graph is None:
			self._data[community_id].graph = graph
		return self._data[community_id]

	def add_author(self, community_id: int, author: Author, graph: ig.Graph) -> None:
		self.get(community_id, graph).add_author(author)
		self._author_index[author.orcid] = community_id

	def add_coauthorship(self, community_id: int, coauthorship: CoAuthorship) -> None:  
		self.get(community_id).add_coauthorship(coauthorship)

	def find_author_community(self, author: str) -> Optional[int]:
		return self._author_index.get(author)

	def find_by_author(self, author: str) -> Optional[Community]:
		community_id = self._author_index.get(author)
		if community_id is None:
			return None
		return self._data[community_id]

	def __getitem__(self, community_id: int) -> Community:
		return self._data[community_id]

	def __contains__(self, community_id: int) -> bool:
		return community_id in self._data

	def __iter__(self) -> Iterator[Community]:
		return iter(self._data.values())

	def __len__(self) -> int:
		return len(self._data)

	def community_ids(self) -> List[int]:
		return list(self._data.keys())

@dataclass
class CommunityNode:
	level: int
	prefix: str
	community: Community
	parent: Optional["CommunityNode"] = None
	children: List["CommunityNode"] = field(default_factory=list)

	def add_child(self, child: "CommunityNode") -> None:
		child.parent = self
		self.children.append(child)

	def is_leaf(self) -> bool:
		return len(self.children) == 0

	def is_root(self) -> bool:
		return self.parent is None

	def walk(self) -> Iterator["CommunityNode"]:
		yield self
		for child in self.children:
			yield from child.walk()

	def indexed_communities(self) -> Dict[str, Community]:
		return {node.prefix: node.community for node in self.walk() if node.prefix != "root"}

	def __repr__(self) -> str:
		return (
			f"CommunityNode(level={self.level}, prefix={self.prefix}, "
			f"id={self.community.id}, size={len(self.community)})"
		)

@dataclass
class CommunityTree:  
	author: Author
	root: CommunityNode
	source_graph: ig.Graph

	def walk(self) -> Iterator[CommunityNode]:
		return self.root.walk()

	@staticmethod
	def prefix_level(prefix: str) -> int:
		if prefix == "root":
			return 0
		return prefix.count(".") + 1

	def indexed_communities(self) -> Dict[str, Community]:
		return self.root.indexed_communities()

	def get_level_nodes(self, level: int) -> List[CommunityNode]:
		return [node for node in self.walk() if node.prefix != "root" and self.prefix_level(node.prefix) == level]

	def get_level_communities(self, level: int) -> Dict[str, Community]:
		return {node.prefix: node.community for node in self.get_level_nodes(level)}

	def get_prefix(self, prefix: str) -> Optional[CommunityNode]:
		for node in self.walk():
			if node.prefix == prefix:
				return node
		return None

	def export_rows(
		self,
		variant: str = "compact",
		author_based: bool = False,
		export_level: Optional[int] = None,
		full_graph: bool = False,
	) -> Dict[str, List[Dict[str, Any]]]:
		if variant not in {"compact", "compact_by_year", "extended_by_year"}:
			raise ValueError("variant must be 'compact', 'compact_by_year', or 'extended_by_year'")

		if full_graph:
			rows = self._serialize_coauthorship_rows(self._graph_coauthorships(), variant, author_based)
			return {"full_graph": rows}

		nodes = self._select_nodes_for_export(export_level)
		return {
			node.prefix: self._serialize_coauthorship_rows(node.community.coauthorships, variant, author_based)
			for node in nodes
		}

	def to_json(
		self,
		variant: str = "compact",
		author_based: bool = False,
		export_level: Optional[int] = None,
		full_graph: bool = False,
		pretty: bool = False,
	) -> Dict[str, List[Dict[str, Any]]] | str:
		exported = self.export_rows(
			variant=variant,
			author_based=author_based,
			export_level=export_level,
			full_graph=full_graph,
		)
		return json.dumps(exported, indent=2, ensure_ascii=False) if pretty else exported

	def to_csv(
		self,
		variant: str = "compact",
		author_based: bool = False,
		export_level: Optional[int] = None,
		full_graph: bool = False,
	) -> Dict[str, str]:
		exported = self.export_rows(
			variant=variant,
			author_based=author_based,
			export_level=export_level,
			full_graph=full_graph,
		)
		return {key: self._rows_to_csv(rows) for key, rows in exported.items()}

	def _select_nodes_for_export(self, export_level: Optional[int]) -> List[CommunityNode]:
		nodes = [node for node in self.walk() if node.prefix != "root"]
		if export_level is None:
			return nodes
		return [node for node in nodes if self.prefix_level(node.prefix) == export_level]

	def _serialize_coauthorship_rows(
		self,
		coauthorships: Iterable[CoAuthorship],
		variant: str,
		author_based: bool,
	) -> List[Dict[str, Any]]:
		rows: List[Dict[str, Any]] = []
		for coauthorship in coauthorships:
			if variant == "compact":
				rows.append(coauthorship.as_compact_row())
			elif variant == "compact_by_year":
				rows.extend(coauthorship.rows_compact_by_year())
			else:
				rows.extend(coauthorship.rows_extended_by_year())
		if author_based:
			rows = self._to_author_based_rows(rows, self.author.orcid)
		return rows

	def _graph_coauthorships(self) -> List[CoAuthorship]:  
		finder = CommunitiesFinder(graph=self.source_graph, algorithm=None, weights=False)
		return list(finder._iter_graph_coauthorships())

	def _to_author_based_rows(self, rows: List[Dict[str, Any]], author_orcid: str) -> List[Dict[str, Any]]:
		normalized: List[Dict[str, Any]] = []
		for row in rows:
			source = row.get("source")
			target = row.get("target")
			if source != author_orcid and target != author_orcid:
				continue
			updated = dict(row)
			if target == author_orcid and source != author_orcid:
				updated["source"], updated["target"] = author_orcid, source
			else:
				updated["source"], updated["target"] = author_orcid, target
			normalized.append(updated)
		return normalized

	def _rows_to_csv(self, rows: List[Dict[str, Any]]) -> str:
		if not rows:
			return ""
		headers: List[str] = []
		for row in rows:
			for key in row.keys():
				if key not in headers:
					headers.append(key)
		buffer = io.StringIO()
		writer = csv.DictWriter(buffer, fieldnames=headers)
		writer.writeheader()
		writer.writerows(rows)
		return buffer.getvalue()

@dataclass
class CommunitiesFinder:
	graph: ig.Graph
	algorithm: Any
	weights: bool = True

	@cached_property
	def partition(self):
		if self.graph.vcount() == 0:
			return None
		if self.weights and "weight" in self.graph.es.attributes():
			return leidenalg.find_partition(self.graph, self.algorithm, weights=self.graph.es["weight"])
		return leidenalg.find_partition(self.graph, self.algorithm)

	def compute_communities(self) -> Communities:
		communities = Communities()
		if self.partition is None:
			return communities

		for v in self.graph.vs:
			community_id = self.partition.membership[v.index]
			author = Author(v["label"], v["name"])
			communities.add_author(community_id, author, self.graph)

		for community in communities:
			author_ids = set(community.authors)

			for e in self.graph.es:
				if "coauthorship" not in e.attributes():
					raise KeyError("Graph edge is missing 'coauthorship' attribute")
				source = self.graph.vs[e.source]["name"]
				target = self.graph.vs[e.target]["name"]

				if source in author_ids and target in author_ids:
					community.add_coauthorship(e["coauthorship"])

		return communities

	def get_author_community(self, author: Author) -> Optional[Community]:
		communities = self.compute_communities()
		community = communities.find_by_author(author.orcid)
		if community is None:
			return None

		indices = [idx for idx, name in enumerate(self.graph.vs["name"]) if name in community.authors]
		if not indices:
			return None

		subgraph = self.graph.subgraph(indices)
		community.graph = subgraph.copy()
		return community

@dataclass
class RecursiveCommunitiesFinder:
	graph: ig.Graph
	algorithm: Any
	weights: bool = True
	min_vertices: int = 2

	def extract(self, author: Author, max_depth: Optional[int] = None) -> Optional[CommunityTree]:  
		root = self._extract_recursive_forest(
			graph=self.graph.copy(),
			author=author,
			prefix="",
			current_depth=1,
			max_depth=max_depth,
			top_level=True,
		)
		if root is None:
			return None
		return CommunityTree(author=author, root=root, source_graph=self.graph.copy())  

	def _extract_recursive_forest(self, graph: ig.Graph, author: Author, prefix: str, current_depth: int, max_depth: Optional[int], top_level: bool = False) -> Optional[CommunityNode]:
		working_graph = graph.copy()
		if working_graph.vcount() <= self.min_vertices:
			return None

		container_prefix = "root" if top_level else prefix
		container_node = CommunityNode(
			level=current_depth - 1 if top_level else current_depth - 1,
			prefix=container_prefix,
			community=Community(id=container_prefix, graph=working_graph.copy()),
		)

		branch_index = 0
		while working_graph.vcount() > self.min_vertices:
			node_prefix = str(branch_index) if top_level else f"{prefix}.{branch_index}"

			finder = CommunitiesFinder(
				graph=working_graph,
				algorithm=self.algorithm,
				weights=self.weights,
			)
			author_community = finder.get_author_community(author)
			if author_community is None:
				break

			author_community.id = node_prefix
			node = CommunityNode(
				level=current_depth,
				prefix=node_prefix,
				community=author_community,
			)

			if max_depth is None or current_depth < max_depth:
				inner_graph = author_community.graph.copy() if author_community.graph is not None else None
				if inner_graph is not None and self.min_vertices < inner_graph.vcount() < working_graph.vcount():
					inner_child = self._extract_recursive_forest(
						graph=inner_graph,
						author=author,
						prefix=node_prefix,
						current_depth=current_depth + 1,
						max_depth=max_depth,
						top_level=False,
					)
					if inner_child is not None:
						for child in inner_child.children:
							node.add_child(child)

			container_node.add_child(node)

			others = [orcid for orcid in author_community.authors if orcid != author.orcid]
			if not others:
				break
			others_set = set(others)
			names_to_remove = [name for name in working_graph.vs["name"] if name in others_set]
			if not names_to_remove:
				break

			before_count = working_graph.vcount()
			working_graph.delete_vertices(names_to_remove)
			if working_graph.vcount() == before_count:
				break

			branch_index += 1

		return container_node if container_node.children else None


### ---- METHODS ----
def get_members(years):
	members = {}
	for year, values in years.items():
		members[year] = values['research-group']
	coauthors_per_year = {}
	return members

def get_coauthors_per_year(coauthorships, ego):
	for coauthor in coauthorships.values():
		#print(type(coauthor))
		if ego == coauthor.source or ego == coauthor.target:
			for edge in coauthor.edges:
				year = edge.year
				if not year in coauthors_per_year: coauthors_per_year[year] = set()
				coauthors_per_year[year].add(coauthor.source.orcid)
				coauthors_per_year[year].add(coauthor.target.orcid)

def compute_temporal_research_groups(communities, threshold):
    years = {}
    authors = {}
    output_works = {}
    for comm_id, com in communities.indexed_communities().items():
        research_group = {}
        collaboration = {}

        for coauthorship in com.coauthorships:
            if coauthorship.source == ego or coauthorship.target == ego:
                authors[coauthorship.source.orcid] = coauthorship.source.name
                authors[coauthorship.target.orcid] = coauthorship.target.name
                coauthorship.edges.sort_by("year")

                works_data = {}
                weights = {}
                for edge in coauthorship.edges:
                    year = edge.year
                    if year not in years:
                        years[year] = {
                            'total-works': total_works_by_year.get(year, 0),
                            'edges': [],
                            'research-group': [],
                            'collaboration': [],
                        }
                    if year not in works_data:
                        works_data[year] = {'weight': 0, 'works': [], 'types': []}
                        weights[year] = 0
                    works_data[year]['weight'] += 1
                    works_data[year]['works'].append(edge.work['id'])
                    works_data[year]['types'].append(edge.work['type'])
                    output_works[edge.work['id']] = edge.work
                    if edge.work['type'] != "other": weights[year] += 1

                for year, data in weights.items():
                    total_y = total_works_by_year.get(year, 0)
                    impact = data / total_y if total_y != 0 else 0
                    if impact >= threshold:
                        if year not in research_group:
                            research_group[year] = set()
                        research_group[year].add(coauthorship.source)
                        research_group[year].add(coauthorship.target)
                    else:
                        if year not in collaboration:
                            collaboration[year] = set()
                        if coauthorship.source != ego:
                            collaboration[year].add(coauthorship.source)
                        else:
                            collaboration[year].add(coauthorship.target)

                    years[year]['edges'].append({
                        'source': coauthorship.source.orcid,
                        'target': coauthorship.target.orcid,
                        'weight': works_data[year]['weight'],
                        'types': works_data[year]['types'],
                        'community': comm_id,
                        'works': works_data[year]['works'],
                    })

        for year, members in research_group.items():
            for member in members:
                years[year]['research-group'].append(member.orcid)
        for year, members in collaboration.items():
            for member in members:
                years[year]['collaboration'].append(member.orcid)
    years = dict(sorted(years.items(), key=lambda x: x[0]))
    return years, authors, output_works

def is_connected(group_members, start_year, end_year, years):
    for y in range(start_year + 1, end_year):
        if y in years:
            coauthors = years[y]
            #print(coauthors, group_members)
            active = group_members & coauthors
            
            # almeno 2 membri oppure ego + 1
            if len(active) >= 2:
                return True
    
    return False

def assemble_research_groups(members, communities, ego, years):
    ALLOW_GAP = 1
    MIN_GROUP_SIZE = 2
    EGO_ID = ego

    yearly_groups = {int(k): set(v) for k, v in members.items()}

    author_to_comms = defaultdict(set)

    for id, community in communities.indexed_communities().items():
        #print(community.authors)
        for a in community.authors:
            #print(a)
            author_to_comms[a].add(id)

    year_comm_groups = defaultdict(dict)

    for y, ymembers in yearly_groups.items():
        temp = defaultdict(set)
        
        for a in ymembers:
            if a in author_to_comms:
                for c in author_to_comms[a]:
                    temp[c].add(a)
        seen = set()
        valid_groups = {}
        
        for c, group in temp.items():
            key = tuple(sorted(group))
            
            if key not in seen and len(group) >= MIN_GROUP_SIZE:
                valid_groups[c] = group
                seen.add(key)
        
        if not valid_groups:
            if len(ymembers) >= MIN_GROUP_SIZE:
                valid_groups["fallback"] = set(ymembers)
            else:
                valid_groups = {}
        
        year_comm_groups[y] = valid_groups

    groups = []
    active = {}

    years_sorted = sorted(year_comm_groups.keys())

    for y in years_sorted:
    
        current_year_groups = year_comm_groups[y]
        new_active = {}
        
        for c, ymembers in current_year_groups.items():
            
            if c in active:
                g = active[c]
                
                # nuova logica continuità
                gap = y - g["end"]
                
                if (gap <= ALLOW_GAP
                    or is_connected(g["last_members"], g["end"], y, years)
                ):
                    #print(f"Inserisco membri che hanno gap: {gap} nell'anno {y} -> {" ".join([ego_coauthors[m].name for m in ymembers])}")
                    g["end"] = y
                    g["members"].update(ymembers)
                    g["last_members"] = set(ymembers)   # aggiorna core recente
                    new_active[c] = g
                else:
                    groups.append(g)
                    new_active[c] = {
                        "start": y,
                        "end": y,
                        "members": set(ymembers),
                        "last_members": set(ymembers)
                    }
            else:
                new_active[c] = {
                    "start": y,
                    "end": y,
                    "members": set(ymembers),
                    "last_members": set(ymembers)
                }
        
        # close not continuative groups
        if current_year_groups:
            for c, g in active.items():
                if c not in new_active:
                    groups.append(g)
        else:
            new_active = active
        
        active = new_active

    for g in active.values():
        groups.append(g)

    final_groups = []
    
    groups = [g for g in groups if len(g["members"]) >= MIN_GROUP_SIZE]
    
    final_groups = []

    for g in groups:
        found = False
        
        for fg in final_groups:
            if g["members"] == fg["members"]:
                fg["start"] = min(fg["start"], g["start"])
                fg["end"] = max(fg["end"], g["end"])
                found = True
                break
        
        if not found:
            final_groups.append(g)
    
    final_groups = sorted(final_groups, key=lambda x: x["start"])
    return final_groups

def compute_coauthorships(products, authors):
	coauthorships = {}
	for w_id, w in tqdm(products.items(), desc="Retrieving coauthorships from products"):
		work_authors = set()
		year = int(w['publicationDate'].split("-")[0]) if "publicationDate" in w and w['publicationDate'] is not None else 9999999
		w_authors = w['authors'] if isinstance(w['authors'], list) else json.loads(w['authors'])
		for author in w_authors:
			if "pid" in author and author['pid'] is not None: 
				if "orcid" in author['pid']['id']['scheme']:
					a = Author(author['fullName'], author['pid']['id']['value'])
					work_authors.add(a)
		items = list(work_authors)
		#print(items)
		permutations = [(items[i], items[j]) for i in range(len(items)) for j in range(i+1, len(items))]
		for nodes in permutations:
			if nodes[0] in authors and nodes[1] in authors:
				source, target= authors[nodes[0].orcid], authors[nodes[1].orcid]
				if year != 9999999:
					edge = Edge(nodes[0], nodes[1],datetime.strptime(w['publicationDate'],"%Y-%m-%d"), work={'id': w_id, 'title': w['mainTitle'], 'type': w['type']})
					comb1 = (source, target)
					comb2 = (target, source)
					if comb1 in coauthorships:
						coauthors = coauthorships[comb1]
						coauthors.add_edge(edge)
					elif comb2 in coauthorships:
						coauthors = coauthorships[comb2]
						coauthors.add_edge(edge)
					else:
						coauthors = CoAuthorship(source, target)
						coauthorships[comb1] = coauthors
						coauthors.add_edge(edge)
	return coauthorships

def build_network(coauthorships):
	g = ig.Graph()
	seen = set()

	for _, coauthors in coauthorships.items():
		s_orcid = coauthors.source.orcid
		t_orcid = coauthors.target.orcid

		if s_orcid not in seen:
			g.add_vertex(name=s_orcid, label=coauthors.source.name)
			seen.add(s_orcid)

		if t_orcid not in seen:
			g.add_vertex(name=t_orcid, label=coauthors.target.name)
			seen.add(t_orcid)

		g.add_edge(s_orcid, t_orcid, weight=coauthors.weight, coauthorship=coauthors)
	return g
