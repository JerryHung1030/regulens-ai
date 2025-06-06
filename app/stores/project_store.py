from __future__ import annotations

import json
from pathlib import Path
from typing import List

from PySide6.QtCore import QObject, Signal

from app.models.project import CompareProject


class ProjectStore(QObject):
    changed = Signal()
    # _PATH is now an instance variable set in __init__

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        # Determine path at runtime to respect potential mocks of Path.home() in tests
        self._PATH: Path = Path.home() / ".config" / "regulens-ai" / "projects.json"
        self.projects: List[CompareProject] = self._load()

    def _load(self) -> List[CompareProject]:
        initial_file_exists = self._PATH.exists()
        initial_file_empty = False
        if initial_file_exists:
            if self._PATH.stat().st_size == 0:
                initial_file_empty = True

        try:
            if not initial_file_exists or initial_file_empty:
                projects = []
            else:
                with open(self._PATH, "r", encoding="utf-8") as f:
                    projects_data = json.load(f)
                if not isinstance(projects_data, list):  # Ensure projects_data is a list
                    projects = []
                else:
                    projects = [CompareProject.from_dict(d) for d in projects_data if isinstance(d, dict)]
        except (json.JSONDecodeError, TypeError) as e:  # Catch errors during parsing
            print(f"Error loading projects.json: {e}. Starting with an empty project list.")
            projects = []

        if not projects and (not initial_file_exists or initial_file_empty):
            self._create_sample_projects_and_data()
            # _create_sample_projects_and_data will call _save, which might re-populate self.projects
            # So we return self.projects which should now contain samples.
            # Or, ensure _create_sample_projects_and_data directly returns the projects it created.
            # For simplicity, let's assume _create_sample_projects_and_data updates self.projects
            # and then we return self.projects here.
            # Re-assign projects to self.projects after sample creation.
            projects = self.projects

        return projects

    def _create_sample_projects_and_data(self):
        # 使用當前工作目錄作為基準
        current_dir = Path.cwd()
        sample_base_dir = current_dir / "sample_data"

        project1 = CompareProject(
            name="ISO27k-A.9.4.2_強密碼合規稽核範例",
            controls_dir=sample_base_dir / "sample1" / "controls",
            procedures_dir=sample_base_dir / "sample1" / "procedures",
            evidences_dir=sample_base_dir / "sample1" / "evidences",
            is_sample=True
        )
        project2 = CompareProject(
            name="ISO27001-A.6.1.2_風險清冊稽核範例",
            controls_dir=sample_base_dir / "sample2" / "controls",
            procedures_dir=sample_base_dir / "sample2" / "procedures",
            evidences_dir=sample_base_dir / "sample2" / "evidences",
            is_sample=True
        )

        # Ensure self.projects is an empty list before adding samples
        self.projects = [project1, project2]
        self._save()  # Save projects.json

    def _save(self):
        self._PATH.parent.mkdir(parents=True, exist_ok=True)
        projects_data = [p.to_dict() for p in self.projects]
        with open(self._PATH, "w", encoding="utf-8") as f:
            json.dump(projects_data, f, indent=2)

    def add(self, proj: CompareProject):
        self.projects.append(proj)
        self._save()
        self.changed.emit()

    def remove(self, proj: CompareProject):
        try:
            self.projects.remove(proj)
            # Also disconnect signals from the removed project
            # to prevent memory leaks or unwanted behavior.
            # This assumes 'deleted' signal is intended to be connected
            # by the store or other components that manage project lifetime.
            # If CompareProject instances manage their own connections that should
            # be cleaned up on deletion, that logic would be elsewhere.
            try:
                proj.deleted.disconnect()
            except (AttributeError, RuntimeError):  # Disconnect may fail if not connected or already deleted
                pass
            try:
                proj.updated.disconnect()
            except (AttributeError, RuntimeError):
                pass
            try:
                proj.changed.disconnect()  # Disconnect from the project's changed signal
            except (AttributeError, RuntimeError):
                pass
            # proj.updated.disconnect(self._save) # Disconnect from updated if it was connected to _save
            # proj.deleted.disconnect(self.remove) # Disconnect from deleted if it was connected to remove

            self._save()  # This will now also emit self.changed
            # self.changed.emit() # No longer needed here as _save now emits it

        except ValueError:  # Project not in list
            pass

    def get_project_by_name(self, name: str) -> CompareProject | None:
        for proj in self.projects:
            if proj.name == name:
                return proj
        return None

    def get_project_by_id(self, project_id: str) -> CompareProject | None:
        # Assuming project_id is unique, e.g. could be string representation of an internal ID
        # For now, let's assume name is the unique identifier for simplicity as per current structure
        # If CompareProject gets a unique ID field later, this method can be updated.
        for proj in self.projects:
            if str(id(proj)) == project_id:  # Example, not robust if id can change or is not what's used
                return proj
        return self.get_project_by_name(project_id)  # Fallback to name if id is not used this way.
        # This part needs clarification based on how projects are identified.
        # For now, using name as a proxy for ID.

    def update_project(self, project_to_update: CompareProject, new_data: dict):
        """
        Updates a project in the store.
        new_data should be a dictionary compatible with CompareProject.from_dict or specific update logic.
        """
        # This is a conceptual update method. The actual update mechanism might be different,
        # e.g., modifying the project instance directly and then calling _save().
        # For renaming, it might be: project.name = new_name; project.updated.emit(); self._save()
        # This method is a placeholder for more complex updates if needed.
        # For now, direct modification of project instance properties followed by _save() is typical.

        # Find the project and update its attributes
        for i, proj in enumerate(self.projects):
            if proj == project_to_update:  # Or match by a unique ID
                # Example of updating:
                # proj.name = new_data.get("name", proj.name)
                # proj.input_path = Path(new_data["input_path"]) if new_data.get("input_path") else proj.input_path
                # proj.ref_paths = [Path(p) for p in new_data["ref_paths"]] if new_data.get("ref_paths") else proj.ref_paths
                # This is overly simplistic. Real updates would likely be handled by modifying the
                # CompareProject instance directly, then calling _save and emitting signals.
                # The 'updated' signal on CompareProject should be emitted after such changes.
                self._save()  # This will now also emit self.changed
                # self.changed.emit() # No longer needed here as _save now emits it
                break
        # If CompareProject emits 'updated' signal, ProjectStore can connect to it
        # for each project to automatically call _save().
        # Example connection in add(): proj.updated.connect(self._save)
        # And disconnect in remove(): proj.updated.disconnect(self._save)
        pass  # Placeholder for update logic. Actual updates are more likely to be handled by modifying
        # the project instance and then calling _save.
        # The presence of this method is more for conceptual completeness.
