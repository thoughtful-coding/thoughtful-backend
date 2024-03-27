#!/usr/bin/env python3
import logging

import numpy as np
import pandas as pd
from stl import mesh
import art


from aws_src_sample.s3.object_inputter import ObjectInputter
from aws_src_sample.s3.object_outputter import ObjectOutputter
from aws_src_sample.utils.aws_env_vars import get_output_bucket_name, get_file_type_counter_table_name

from aws_src_sample.dynamodb.file_type_counter_table import FileTypeCounterTable

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)


def create_mesh_helper(input_csv_path: str, output_stl_path: str) -> None:

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


def create_mesh(
    object_inputter: ObjectInputter,
    object_outputter: ObjectOutputter,
    input_bucket_name: str,
    input_bucket_key: str,
    output_bucket_name: str,
) -> None:
    input_data = object_inputter.get(bucket=input_bucket_name, key=input_bucket_key)

    file_reader_file_name = "temp.csv"

    with open("/tmp/" + file_reader_file_name, "w") as tmp_fp:
        tmp_fp.write(input_data)

    output_bucket_key = input_bucket_key[:-4] + ".stl"
    temp_input_path = "/tmp/" + file_reader_file_name
    temp_output_path = "/tmp/" + output_bucket_key
    create_mesh_helper(temp_input_path, temp_output_path)

    with open(temp_output_path, "rb") as file:
        file_contents = file.read()

    object_outputter.put(
        bucket=output_bucket_name,
        key=output_bucket_key,
        contents=file_contents,
    )


def create_ascii_art(
    object_inputter: ObjectInputter,
    object_outputter: ObjectOutputter,
    input_bucket_name: str,
    input_bucket_key: str,
    output_bucket_name: str,
) -> None:

    input_data = object_inputter.get(bucket=input_bucket_name, key=input_bucket_key)
    file_contents = art(input_data)
    # file_reader_file_name = "temp.txt"

    # with open("/tmp/" + file_reader_file_name, "w") as tmp_fp:
    #    tmp_fp.write(input_data)

    output_bucket_key = input_bucket_key[:-4] + ".txt"
    # temp_input_path = "/tmp/" + file_reader_file_name
    # temp_output_path = "/tmp/" + output_bucket_key
    object_outputter.put(
        bucket=output_bucket_name,
        key=output_bucket_key,
        contents=file_contents,
    )


def create_instructions(
    object_inputter: ObjectInputter,
    object_outputter: ObjectOutputter,
    input_bucket_name: str,
    input_bucket_key: str,
    output_bucket_name: str,
) -> None:
    object_outputter.put(
        bucket=output_bucket_name,
        key="instructions.txt",
        contents="lorem ipsum asjhdkajsdhkajshd",
    )


FN_INTERFACE = {"csv": create_mesh, "txt": create_ascii_art}
# FILE_TYPES = {"csv":"stl","txt":"txt"}


class LambdaHandler:
    def __init__(
        self,
        object_inputter: ObjectInputter,
        object_outputter: ObjectOutputter,
        file_type_counter_table: FileTypeCounterTable,
    ) -> None:
        self.object_inputter = object_inputter
        self.object_outputter = object_outputter
        self.file_type_counter_table = file_type_counter_table

    def handle(self, event: dict) -> dict:
        input_bucket = event["Records"][0]["s3"]["bucket"]["name"]
        input_key = event["Records"][0]["s3"]["object"]["key"]
        output_bucket_name = get_output_bucket_name()

        input_file_type = str(input_key.split(".")[-1])

        # Get our bucket and file name
        print("decision", input_file_type)
        if input_file_type not in FN_INTERFACE:
            print("invalid file")
            create_instructions(
                self.object_inputter, self.object_outputter, input_bucket, input_key, output_bucket_name
            )
        else:
            print("valid file", FN_INTERFACE[input_file_type])
            FN_INTERFACE[input_file_type](
                self.object_inputter, self.object_outputter, input_bucket, input_key, output_bucket_name
            )
            self.file_type_counter_table.increment(item_key=input_file_type)

        return {"statusCode": 200}


def lambda_handler(event: dict, context) -> dict:

    _LOGGER.info(event)

    lh = LambdaHandler(
        ObjectInputter(),
        ObjectOutputter(),
        FileTypeCounterTable(get_file_type_counter_table_name()),
    )
    return lh.handle(event)
