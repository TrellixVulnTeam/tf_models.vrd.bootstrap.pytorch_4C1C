# Copyright 2018 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
r"""Runs evaluation using OpenImages groundtruth and predictions.

Example usage:
python \
models/research/object_detection/metrics/oid_vrd_challenge_evaluation.py \
    --input_annotations_boxes=/path/to/input/annotations-human-bbox.csv \
    --input_annotations_labels=/path/to/input/annotations-label.csv \
    --input_class_labelmap=/path/to/input/class_labelmap.pbtxt \
    --input_relationship_labelmap=/path/to/input/relationship_labelmap.pbtxt \
    --input_predictions=/path/to/input/predictions.csv \
    --output_metrics=/path/to/output/metric.csv \

CSVs with bounding box annotations and image label (including the image URLs)
can be downloaded from the Open Images Challenge website:
https://storage.googleapis.com/openimages/web/challenge.html
The format of the input csv and the metrics itself are described on the
challenge website.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import argparse
import pandas as pd
from google.protobuf import text_format
from tqdm import tqdm

from object_detection.metrics import io_utils
from object_detection.metrics import oid_vrd_challenge_evaluation_utils as utils
from object_detection.protos import string_int_label_map_pb2
from object_detection.utils import vrd_evaluation

from bootstrap.lib.logger import Logger

def _load_labelmap(labelmap_path):
  """Loads labelmap from the labelmap path.

  Args:
    labelmap_path: Path to the labelmap.

  Returns:
    A dictionary mapping class name to class numerical id.
  """

  label_map = string_int_label_map_pb2.StringIntLabelMap()
  with open(labelmap_path, 'r') as fid:
    label_map_string = fid.read()
    text_format.Merge(label_map_string, label_map)
  labelmap_dict = {}
  for item in label_map.item:
    labelmap_dict[item.name] = item.id
  return labelmap_dict


def _swap_labelmap_dict(labelmap_dict):
  """Swaps keys and labels in labelmap.

  Args:
    labelmap_dict: Input dictionary.

  Returns:
    A dictionary mapping class name to class numerical id.
  """
  return {v:k for k, v in labelmap_dict.items()}


def main(parsed_args):
  dir_exp = os.path.dirname(parsed_args.output_metrics)
  name = os.path.basename(parsed_args.output_metrics).split('.json')[0]
  Logger(dir_exp, name=name) # create/load logs

  Logger()('Begin evaluation')

  all_box_annotations = pd.read_csv(parsed_args.input_annotations_boxes)
  all_label_annotations = pd.read_csv(parsed_args.input_annotations_labels)
  all_annotations = pd.concat([all_box_annotations, all_label_annotations], sort=True)

  class_label_map = _load_labelmap(parsed_args.input_class_labelmap)
  relationship_label_map = _load_labelmap(
      parsed_args.input_relationship_labelmap)

  relation_evaluator = vrd_evaluation.VRDRelationDetectionEvaluator()
  phrase_evaluator = vrd_evaluation.VRDPhraseDetectionEvaluator()

  for _, groundtruth in enumerate(all_annotations.groupby('ImageID')):
    image_id, image_groundtruth = groundtruth
    groundtruth_dictionary = utils.build_groundtruth_vrd_dictionary(
        image_groundtruth, class_label_map, relationship_label_map)

    relation_evaluator.add_single_ground_truth_image_info(
        image_id, groundtruth_dictionary)
    phrase_evaluator.add_single_ground_truth_image_info(image_id,
                                                        groundtruth_dictionary)

  all_predictions = pd.read_csv(parsed_args.input_predictions)
  for _, prediction_data in enumerate(all_predictions.groupby('ImageID')):
    image_id, image_predictions = prediction_data
    prediction_dictionary = utils.build_predictions_vrd_dictionary(
        image_predictions, class_label_map, relationship_label_map)

    relation_evaluator.add_single_detected_image_info(image_id,
                                                      prediction_dictionary)
    phrase_evaluator.add_single_detected_image_info(image_id,
                                                    prediction_dictionary)

  relation_metrics = relation_evaluator.evaluate(
      relationships=_swap_labelmap_dict(relationship_label_map))
  phrase_metrics = phrase_evaluator.evaluate(
      relationships=_swap_labelmap_dict(relationship_label_map))

  for k,v in relation_metrics.items():
    Logger().log_value('eval_epoch.{}'.format(k), v)

  for k,v in phrase_metrics.items():
    Logger().log_value('eval_epoch.{}'.format(k), v)

  score = relation_metrics['VRDMetric_Relationships_mAP@0.5IOU'] * 0.4
  score += relation_metrics['VRDMetric_Relationships_Recall@50@0.5IOU'] * 0.2
  score += phrase_metrics['VRDMetric_Phrases_mAP@0.5IOU'] * 0.4
  Logger().log_value('eval_epoch.score', score)
  epoch_id = len(Logger().values['eval_epoch.score']) - 1
  Logger().log_value('eval_epoch.epoch', epoch_id)

  Logger().flush()

  Logger()('End evaluation')
  # with open(parsed_args.output_metrics, 'w') as fid:
  #   io_utils.write_csv(fid, relation_metrics)
  #   io_utils.write_csv(fid, phrase_metrics)


if __name__ == '__main__':

  parser = argparse.ArgumentParser(
      description=
      'Evaluate Open Images Visual Relationship Detection predictions.')
  parser.add_argument(
      '--input_annotations_boxes',
      required=True,
      help='File with groundtruth vrd annotations.')
  parser.add_argument(
      '--input_annotations_labels',
      required=True,
      help='File with groundtruth labels annotations')
  parser.add_argument(
      '--input_predictions',
      required=True,
      help="""File with detection predictions; NOTE: no postprocessing is
      applied in the evaluation script.""")
  parser.add_argument(
      '--input_class_labelmap',
      required=True,
      help="""OpenImages Challenge labelmap; note: it is expected to include
      attributes.""")
  parser.add_argument(
      '--input_relationship_labelmap',
      required=True,
      help="""OpenImages Challenge relationship labelmap.""")
  parser.add_argument(
      '--output_metrics', required=True, help='Output file with json metrics')
  args = parser.parse_args()
  main(args)
