#!/usr/bin/env python3
import logging

import numpy as np
import pandas as pd
from stl import mesh

from aws_src_sample.s3.object_inputter import ObjectInputter
from aws_src_sample.s3.object_outputter import ObjectOutputter
from aws_src_sample.utils.aws_env_vars import get_output_bucket_name

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)


def create_mesh(input_csv_path: str, output_stl_path: str) -> None:
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


class LambdaHandler:
    def __init__(
        self,
        object_inputter: ObjectInputter,
        object_outputter: ObjectOutputter,
    ) -> None:
        self.object_inputter = object_inputter
        self.object_outputter = object_outputter

    def handle(self, event: dict) -> dict:
        input_bucket = event["Records"][0]["s3"]["bucket"]["name"]
        input_key = event["Records"][0]["s3"]["object"]["key"]
        output_bucket_name = get_output_bucket_name()

        input_data = self.object_inputter.get(bucket=input_bucket, key=input_key)

        # Get our bucket and file name
        output_file_name = "temp.csv"

        with open("/tmp/" + output_file_name, "w") as tmp_fp:
            tmp_fp.write(input_data)

        write_key = input_key[:-4] + ".stl"
        stl_path = "/tmp/" + write_key
        create_mesh("/tmp/" + output_file_name, stl_path)

        with open(stl_path, "rb") as file:
            file_contents = file.read()

        self.object_outputter.put(
            bucket=output_bucket_name,
            key=write_key,
            contents=file_contents,
        )

        return {"statusCode": 200}


def lambda_handler(event: dict, context) -> dict:
    _LOGGER.info(event)

    lh = LambdaHandler(
        ObjectInputter(),
        ObjectOutputter(),
    )
    return lh.handle(event)
