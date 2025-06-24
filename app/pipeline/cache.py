import hashlib
import gzip
import json
from pathlib import Path
from typing import Optional, Type, TypeVar
import numpy as np
from pydantic import BaseModel

# Add this import
from app.app_paths import get_app_data_dir

# For generic type hinting of BaseModel subtypes
T = TypeVar('T', bound=BaseModel)


class CacheService:
    def __init__(self, project_name: str): # Modified constructor
        # Modified to use project-specific cache directory within app_data_dir
        self.cache_dir = get_app_data_dir() / "cache" / "embeddings" / project_name
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def generate_key(*args: str) -> str:
        """
        Generates a SHA-256 hash key from one or more string arguments.
        """
        s = "".join(args)
        return hashlib.sha256(s.encode('utf-8')).hexdigest()

    def save_json(self, key: str, data: BaseModel) -> None:
        """
        Serializes a Pydantic model to JSON, compresses it, and saves to cache.
        """
        file_path = self.cache_dir / f"{key}.json.gz"
        try:
            json_data = data.model_dump_json()
            with gzip.open(file_path, 'wt', encoding='utf-8') as f:
                f.write(json_data)
            # print(f"Saved JSON data to {file_path}")
        except IOError as e:
            print(f"Error saving JSON data to {file_path}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while saving JSON {file_path}: {e}")

    def load_json(self, key: str, model_type: Type[T]) -> Optional[T]:
        """
        Loads, decompresses, and deserializes JSON data from cache into a Pydantic model.
        """
        file_path = self.cache_dir / f"{key}.json.gz"
        if not file_path.exists():
            # print(f"JSON cache file not found: {file_path}")
            return None
        try:
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                json_data = f.read()
            return model_type.model_validate_json(json_data)
        except IOError as e:
            print(f"Error loading JSON data from {file_path}: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {file_path}: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred while loading JSON {file_path}: {e}")
            return None

    def save_numpy(self, key: str, array: np.ndarray) -> None:
        """
        Saves a NumPy array to cache.
        """
        file_path = self.cache_dir / f"{key}.npy"
        try:
            np.save(file_path, array)
            # print(f"Saved NumPy array to {file_path}")
        except IOError as e:
            print(f"Error saving NumPy array to {file_path}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while saving NumPy array {file_path}: {e}")

    def load_numpy(self, key: str) -> Optional[np.ndarray]:
        """
        Loads a NumPy array from cache.
        """
        file_path = self.cache_dir / f"{key}.npy"
        if not file_path.exists():
            # print(f"NumPy cache file not found: {file_path}")
            return None
        try:
            return np.load(file_path)
        except IOError as e:
            print(f"Error loading NumPy array from {file_path}: {e}")
            return None
        except Exception as e:  # Catch other potential errors like unpickling errors
            print(f"An unexpected error occurred while loading NumPy array {file_path}: {e}")
            return None

    def exists(self, key: str, extension: str) -> bool:
        """
        Checks if a cache file with the given key and extension exists.
        """
        file_path = self.cache_dir / f"{key}.{extension}"
        return file_path.exists()


if __name__ == '__main__':
    # Example Usage (conceptual):
    
    class MyPydanticModel(BaseModel):
        name: str
        value: int
        items: list[str]

    # Create a cache service instance for a dummy project
    # This now requires a project_name
    dummy_project_name = "test_project_cache" 
    cache_service = CacheService(project_name=dummy_project_name)
    print(f"Cache directory being used for test_project_cache: {cache_service.cache_dir}")

    # Test JSON caching
    print("Testing JSON Caching...")
    json_model_instance = MyPydanticModel(name="Test Model", value=123, items=["a", "b", "c"])
    json_key_str = "my_test_model_data"
    
    # Use generate_key for a more robust key
    json_key = cache_service.generate_key(json_key_str, "model_version_1")

    print(f"Saving JSON with key: {json_key}")
    cache_service.save_json(json_key, json_model_instance)

    print(f"Checking existence for JSON key {json_key}.json.gz: {cache_service.exists(json_key, 'json.gz')}")

    print(f"Loading JSON with key: {json_key}")
    loaded_model_instance = cache_service.load_json(json_key, MyPydanticModel)

    if loaded_model_instance:
        print(f"Loaded model: {loaded_model_instance}")
        assert loaded_model_instance.name == "Test Model"
        assert loaded_model_instance.value == 123
    else:
        print("Failed to load JSON model.")

    # Test NumPy caching
    print("\nTesting NumPy Caching...")
    numpy_array_instance = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32)
    npy_key_str = "my_test_numpy_array"
    
    # Use generate_key
    npy_key = cache_service.generate_key(npy_key_str, "array_type_float32")
    
    print(f"Saving NumPy array with key: {npy_key}")
    cache_service.save_numpy(npy_key, numpy_array_instance)

    print(f"Checking existence for NumPy key {npy_key}.npy: {cache_service.exists(npy_key, 'npy')}")

    print(f"Loading NumPy array with key: {npy_key}")
    loaded_numpy_array = cache_service.load_numpy(npy_key)

    if loaded_numpy_array is not None:
        print(f"Loaded NumPy array:\n{loaded_numpy_array}")
        assert np.array_equal(loaded_numpy_array, numpy_array_instance)
    else:
        print("Failed to load NumPy array.")

    # Test non-existent key
    print("\nTesting non-existent keys...")
    non_existent_json_key = cache_service.generate_key("non_existent_json")
    print(f"Loading non-existent JSON: {cache_service.load_json(non_existent_json_key, MyPydanticModel)}")
    print(f"Checking existence for non-existent JSON: {cache_service.exists(non_existent_json_key, 'json.gz')}")

    non_existent_npy_key = cache_service.generate_key("non_existent_npy")
    print(f"Loading non-existent NumPy: {cache_service.load_numpy(non_existent_npy_key)}")
    print(f"Checking existence for non-existent NumPy: {cache_service.exists(non_existent_npy_key, 'npy')}")
    
    # Cleanup for __main__ example (optional)
    # import shutil
    # test_project_cache_path = get_app_data_dir() / "cache" / "embeddings" / dummy_project_name
    # if test_project_cache_path.exists():
    #     print(f"\nCleaning up temporary cache directory: {test_project_cache_path}")
    #     shutil.rmtree(test_project_cache_path)
    print("\nCacheService tests finished.")
