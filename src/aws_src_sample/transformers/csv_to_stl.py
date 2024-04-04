import random

import numpy as np
import pandas as pd
from stl import mesh

from aws_src_sample.transformers.transformer import Transformer


class CSVToSTLTransformer(Transformer):

    @staticmethod
    def _create_mesh_helper(input_csv_path: str, output_stl_path: str) -> None:

        # Load your CSV file
        data = pd.read_csv(input_csv_path, header=None)

        # Create a grid of points (meshgrid)
        x = np.arange(data.shape[1])
        y = np.arange(data.shape[0])
        X, Y = np.meshgrid(x, y)
        Z = data.values

        # Create a set of vertices. Each point is a vertex
        surface_vertices = np.vstack([X.ravel(), Y.ravel(), Z.ravel()]).T
        vertices = np.vstack([surface_vertices])

        # Create faces (triangles) for the STL
        faces: list[list[float]] = []

        # Iterate over the points and create two triangles (faces) per point
        for i in range(X.shape[0] - 1):
            for j in range(X.shape[1] - 1):
                # Define vertices for the two triangles
                # Triangle 1
                v0 = j + i * X.shape[1]
                v1 = v0 + X.shape[1]
                v2 = v0 + 1
                faces.append([v0, v1, v2])

                # Triangle 2
                v3 = v1 + 1
                faces.append([v2, v1, v3])

        # Create the mesh
        your_mesh = mesh.Mesh(np.zeros(len(faces), dtype=mesh.Mesh.dtype))

        # Populate the mesh with vertices and faces
        for i, f in enumerate(faces):
            for j in range(3):
                your_mesh.vectors[i][j] = vertices[f[j], :]

        # Write the mesh to file
        your_mesh.save(output_stl_path)

    @staticmethod
    def transform(input_data: bytes) -> bytes:
        file_reader_file_name = "temp.csv"

        with open("/tmp/" + file_reader_file_name, "wb") as tmp_fp:
            tmp_fp.write(input_data)

        temp_input_path = "/tmp/" + file_reader_file_name
        temp_output_path = "/tmp/" + f"tmp_file{random.randint(0, 1_000_000):08d}"
        CSVToSTLTransformer._create_mesh_helper(temp_input_path, temp_output_path)

        with open(temp_output_path, "rb") as file:
            return file.read()

    @staticmethod
    def get_file_ext() -> str:
        return ".stl"
