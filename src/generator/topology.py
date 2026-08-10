import csv
import os
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class Job:
    job_id: str
    job_name: str
    platform: str
    domain: str
    stage: str
    schedule: str
    criticality: int
    default_duration_sec: int
    owner_team: str
    retry_policy: str
    active: bool

@dataclass
class DependencyEdge:
    edge_id: str
    parent_job_id: str
    child_job_id: str
    dependency_type: str
    max_lag_min: int
    required: bool

@dataclass
class BusinessAsset:
    asset_id: str
    asset_name: str
    asset_type: str
    owner: str
    sla_minutes: int
    criticality: int
    communication_template: str

class Topology:
    def __init__(self, data_dir: str):
        self.jobs: Dict[str, Job] = {}
        self.edges: Dict[str, DependencyEdge] = {}
        self.assets: Dict[str, BusinessAsset] = {}
        self.asset_deps: Dict[str, List[str]] = {} # job_id -> list of asset_ids
        
        self.children: Dict[str, List[DependencyEdge]] = {}
        self.parents: Dict[str, List[DependencyEdge]] = {}
        
        self._load_jobs(os.path.join(data_dir, "jobs.csv"))
        self._load_dependencies(os.path.join(data_dir, "dependencies.csv"))
        self._load_business_assets(os.path.join(data_dir, "business_assets.csv"))
        self._load_asset_dependencies(os.path.join(data_dir, "asset_dependencies.csv"))
        
    def _parse_bool(self, val: str) -> bool:
        return val.lower() == 'true'

    def _load_jobs(self, filepath: str):
        if not os.path.exists(filepath):
            return
        with open(filepath, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                job = Job(
                    job_id=row['job_id'],
                    job_name=row['job_name'],
                    platform=row['platform'],
                    domain=row['domain'],
                    stage=row['stage'],
                    schedule=row['schedule'],
                    criticality=int(row['criticality']),
                    default_duration_sec=int(row['default_duration_sec']),
                    owner_team=row['owner_team'],
                    retry_policy=row['retry_policy'],
                    active=self._parse_bool(row['active'])
                )
                self.jobs[job.job_id] = job
                self.children[job.job_id] = []
                self.parents[job.job_id] = []

    def _load_dependencies(self, filepath: str):
        if not os.path.exists(filepath):
            return
        with open(filepath, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                edge = DependencyEdge(
                    edge_id=row['edge_id'],
                    parent_job_id=row['parent_job_id'],
                    child_job_id=row['child_job_id'],
                    dependency_type=row['dependency_type'],
                    max_lag_min=int(row['max_lag_min']),
                    required=self._parse_bool(row['required'])
                )
                self.edges[edge.edge_id] = edge
                if edge.parent_job_id in self.children:
                    self.children[edge.parent_job_id].append(edge)
                if edge.child_job_id in self.parents:
                    self.parents[edge.child_job_id].append(edge)

    def _load_business_assets(self, filepath: str):
        if not os.path.exists(filepath):
            return
        with open(filepath, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                asset = BusinessAsset(
                    asset_id=row['asset_id'],
                    asset_name=row['asset_name'],
                    asset_type=row['asset_type'],
                    owner=row['owner'],
                    sla_minutes=int(row['sla_minutes']),
                    criticality=int(row['criticality']),
                    communication_template=row['communication_template']
                )
                self.assets[asset.asset_id] = asset

    def _load_asset_dependencies(self, filepath: str):
        if not os.path.exists(filepath):
            return
        with open(filepath, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                job_id = row['job_id']
                asset_id = row['asset_id']
                if job_id not in self.asset_deps:
                    self.asset_deps[job_id] = []
                self.asset_deps[job_id].append(asset_id)

    def get_job(self, job_id: str) -> Job:
        return self.jobs.get(job_id)

    def get_children(self, job_id: str) -> List[DependencyEdge]:
        return self.children.get(job_id, [])

    def get_parents(self, job_id: str) -> List[DependencyEdge]:
        return self.parents.get(job_id, [])

    def get_descendants(self, job_id: str) -> List[str]:
        visited = set()
        order = []
        
        def dfs(curr_id):
            if curr_id not in visited:
                visited.add(curr_id)
                for edge in self.get_children(curr_id):
                    dfs(edge.child_job_id)
                order.append(curr_id)
                
        dfs(job_id)
        order.reverse()
        return order[1:]

    def get_ancestors(self, job_id: str) -> List[str]:
        visited = set()
        order = []
        
        def dfs(curr_id):
            if curr_id not in visited:
                visited.add(curr_id)
                for edge in self.get_parents(curr_id):
                    dfs(edge.parent_job_id)
                order.append(curr_id)
                
        dfs(job_id)
        return order[:-1]

    def get_affected_assets(self, job_ids: List[str]) -> List[str]:
        affected = set()
        for jid in job_ids:
            if jid in self.asset_deps:
                affected.update(self.asset_deps[jid])
        return list(affected)

    def topological_sort(self) -> List[str]:
        visited = set()
        temp_mark = set()
        order = []
        
        def visit(n):
            if n in temp_mark:
                return False
            if n not in visited:
                temp_mark.add(n)
                for edge in self.get_children(n):
                    visit(edge.child_job_id)
                temp_mark.remove(n)
                visited.add(n)
                order.insert(0, n)
            return True
            
        for job_id in self.jobs:
            if job_id not in visited:
                visit(job_id)
        return order

    def validate(self) -> List[str]:
        errors = []
        
        for edge_id, edge in self.edges.items():
            if edge.parent_job_id not in self.jobs:
                errors.append(f"Edge {edge_id} references missing parent job {edge.parent_job_id}")
            if edge.child_job_id not in self.jobs:
                errors.append(f"Edge {edge_id} references missing child job {edge.child_job_id}")
                
        for job_id, asset_ids in self.asset_deps.items():
            if job_id not in self.jobs:
                errors.append(f"Asset dependency references missing job {job_id}")
            for asset_id in asset_ids:
                if asset_id not in self.assets:
                    errors.append(f"Job {job_id} references missing asset {asset_id}")
                    
        visited = set()
        temp_mark = set()
        def has_cycle(n):
            if n in temp_mark: return True
            if n in visited: return False
            temp_mark.add(n)
            for edge in self.get_children(n):
                if has_cycle(edge.child_job_id): return True
            temp_mark.remove(n)
            visited.add(n)
            return False
            
        for job_id in self.jobs:
            if job_id not in visited:
                if has_cycle(job_id):
                    errors.append(f"Cycle detected starting at or involving job {job_id}")
                    break
        
        return errors
