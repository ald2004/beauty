import base64
import json
import os
import tempfile
import uuid
from io import BytesIO

import cv2
import numpy as np
# tf
import tensorflow as tf
# from detectron2.config import get_cfg
# from detectron2.data import (
#     DatasetCatalog,
#     MetadataCatalog,
# )
# from detectron2.data.detection_utils import read_image
# pytorch
# from detectron2.engine import DefaultPredictor
from detectron2.utils.visualizer import ColorMode, Visualizer
from detectron2.structures import Instances
from flask import Flask, request, Response
from tensorflow.keras.preprocessing import image
from utils import (
    # setup_logger,
    base64toImageArray,
    YOLO_single_img,
    # myx_Visualizer,
    convertBack,
    convertBackRatio,
    kill_duplicate_by_score,
    # thirteentimestamp,
    # kill_duplicate_by_score
)

os.environ["CUDA_VISIBLE_DEVICES"] = "4"
output_saved_model_dir = './tensorrt_dir'
# from flask_cors import CORS
img_size = 256
_SMALL_OBJECT_AREA_THRESH = 1000
app = Flask(__name__)


# Uncomment this line if you are making a Cross domain request
# CORS(app)
class beauty(object):
    def __init__(self, output_saved_model_dir):
        gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=0.01)
        self.sess = tf.Session(config=tf.ConfigProto(gpu_options=gpu_options))
        self.sess.run(tf.global_variables_initializer())
        tf.saved_model.load(export_dir=output_saved_model_dir, tags=[tf.saved_model.tag_constants.SERVING],
                            sess=self.sess)
        graph = tf.get_default_graph()
        self.X = graph.get_tensor_by_name('X:0')
        self.Y = graph.get_tensor_by_name('Y:0')
        self.Xs = graph.get_tensor_by_name('generator/xs:0')

    def predict(self, X_img, Y_img) -> np.ndarray:
        predictions = self.sess.run(self.Xs, feed_dict={self.X: X_img, self.Y: Y_img})
        # TODO: convert to human-friendly labels
        return predictions

    def preprocess(self, img):
        return (img / 255. - 0.5) * 2

    def deprocess(self, img):
        return (img + 1) / 2


def _create_text_labels(predict):
    ## ('uniform', 0.9847872257232666, (226.92221069335938, 266.7281188964844, 87.1346435546875, 198.78860473632812))
    # ['face-head', 'mask-head', 'face-cap', 'mask-cap']
    # ['不合格', '口罩', '帽子', '合格']
    labels = []
    for p in predict:
        if p[0] == 'mask-cap':
            labels.append('合格')
        else:
            labels.append('不合格')
    return labels


# class kittchen(object):
#     def __init__(self, score_thres):
#         cfg = get_cfg()
#         # cfg.MODEL.DEVICE = "cpu"
#         cfg.merge_from_file("cfg/faster_rcnn_X_101_32x8d_FPN_3x.yaml")
#         cfg.MODEL.ROI_HEADS.BATCH_SIZE_PER_IMAGE = 512  # faster, and good enough for this toy dataset (default: 512)
#         cfg.MODEL.ROI_HEADS.NUM_CLASSES = 4  # only has one class (ballon)
#         # cfg.MODEL.WEIGHTS="output/model_final_11.pth"
#         cfg.MODEL.WEIGHTS = "output/model_final.pth"
#         cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = score_thres
#         self.predictor = DefaultPredictor(cfg)
#         DatasetCatalog.register("chefCap", lambda d: None)
#         self.metadata = MetadataCatalog.get('chefCap')
#         self.metadata.set(thing_classes=['face-head', 'mask-head', 'face-cap', 'mask-cap'])
#
#     def predict(self, img):
#         return self.predictor(img)
#
#     def get_metadata(self):
#         return self.metadata
#
#     def setscore_thres(self, score_thres):
#         self.score_thres = score_thres
#
#     def _create_text_labels(self, classes, scores, class_names=['不合格', '口罩', '帽子', '合格']):
#         # ['face-head', 'mask-head', 'face-cap', 'mask-cap']
#         # ['不合格', '口罩', '帽子', '合格']
#         labels = None
#         if classes is not None and class_names is not None and len(class_names) > 1:
#             labels = [class_names[i] for i in classes]
#         if scores is not None:
#             if labels is None:
#                 labels = ["{:.0f}%".format(s * 100) for s in scores]
#             else:
#                 # labels = ["{} {:.0f}%".format(l, s * 100) for l, s in zip(labels, scores)]
#                 labels = [f"{l}" for l in labels]
#         return labels


# class myx_Visualizer(Visualizer):
#     def overlay_instances(
#             self,
#             *,
#             boxes=None,
#             labels=None,
#             masks=None,
#             keypoints=None,
#             assigned_colors=None,
#             alpha=0.5
#     ):
#
#         num_instances = None
#         if boxes is not None:
#             boxes = self._convert_boxes(boxes)
#             num_instances = len(boxes)
#         if masks is not None:
#             masks = self._convert_masks(masks)
#             if num_instances:
#                 assert len(masks) == num_instances
#             else:
#                 num_instances = len(masks)
#         if keypoints is not None:
#             if num_instances:
#                 assert len(keypoints) == num_instances
#             else:
#                 num_instances = len(keypoints)
#             keypoints = self._convert_keypoints(keypoints)
#         if labels is not None:
#             assert len(labels) == num_instances
#
#         if num_instances == 0:
#             return self.output
#         if boxes is not None and boxes.shape[1] == 5:
#             return self.overlay_rotated_instances(
#                 boxes=boxes, labels=labels, assigned_colors=assigned_colors
#             )
#
#         # Display in largest to smallest order to reduce occlusion.
#         areas = None
#         if boxes is not None:
#             areas = np.prod(boxes[:, 2:] - boxes[:, :2], axis=1)
#         elif masks is not None:
#             areas = np.asarray([x.area() for x in masks])
#         assigned_colors = np.array([
#             [0.667, 0.333, 1.],
#             [0.85, 0.325, 0.098],
#             [0., 0.667, 0.5],
#             [0.749, 0.749, 0.]
#         ], dtype=np.float)
#         if areas is not None:
#             sorted_idxs = np.argsort(-areas).tolist()
#             # Re-order overlapped instances in descending order.
#             boxes = boxes[sorted_idxs] if boxes is not None else None
#             labels = [labels[k] for k in sorted_idxs] if labels is not None else None
#             masks = [masks[idx] for idx in sorted_idxs] if masks is not None else None
#             # assigned_colors = [assigned_colors[idx] for idx in sorted_idxs]
#             keypoints = keypoints[sorted_idxs] if keypoints is not None else None
#
#         color_dic = {'face-head': 0, 'mask-head': 1, 'face-cap': 2, 'mask-cap': 3}
#
#         for i in range(num_instances):
#             #             color = assigned_colors[i]
#             color = assigned_colors[color_dic[labels[i].split(" ")[0]]]
#             #             print(labels[i])
#             #             mask-cap 100%
#             #             mask-cap 82%
#             #             mask-cap 76%
#             #             mask-cap 98%
#             if boxes is not None:
#                 self.draw_box(boxes[i], edge_color=color)
#
#             if masks is not None:
#                 for segment in masks[i].polygons:
#                     self.draw_polygon(segment.reshape(-1, 2), color, alpha=alpha)
#
#             if labels is not None:
#                 # first get a box
#                 if boxes is not None:
#                     x0, y0, x1, y1 = boxes[i]
#                     text_pos = (x0, y0)  # if drawing boxes, put text on the box corner.
#                     horiz_align = "left"
#                 elif masks is not None:
#                     x0, y0, x1, y1 = masks[i].bbox()
#
#                     # draw text in the center (defined by median) when box is not drawn
#                     # median is less sensitive to outliers.
#                     text_pos = np.median(masks[i].mask.nonzero(), axis=1)[::-1]
#                     horiz_align = "center"
#                 else:
#                     continue  # drawing the box confidence for keypoints isn't very useful.
#                 # for small objects, draw text at the side to avoid occlusion
#                 instance_area = (y1 - y0) * (x1 - x0)
#                 if (
#                         instance_area < _SMALL_OBJECT_AREA_THRESH * self.output.scale
#                         or y1 - y0 < 40 * self.output.scale
#                 ):
#                     if y1 >= self.output.height - 5:
#                         text_pos = (x1, y0)
#                     else:
#                         text_pos = (x0, y1)
#
#                 height_ratio = (y1 - y0) / np.sqrt(self.output.height * self.output.width)
#                 lighter_color = self._change_color_brightness(color, brightness_factor=0.7)
#                 font_size = (
#                         np.clip((height_ratio - 0.02) / 0.08 + 1, 1.2, 2)
#                         * 0.5
#                         * self._default_font_size
#                 )
#                 self.draw_text(
#                     labels[i],
#                     text_pos,
#                     color=lighter_color,
#                     horizontal_alignment=horiz_align,
#                     font_size=font_size,
#                 )
#
#         # draw keypoints
#         if keypoints is not None:
#             for keypoints_per_instance in keypoints:
#                 self.draw_and_connect_keypoints(keypoints_per_instance)
#
#         return self.output


# Testing URL
@app.route('/makeup', methods=['POST'])
def hello_world():
    # makeups = glob.glob(os.path.join('imgs', 'makeup', 'ref5.jpg'))  # ref5.jpg is good
    # print('-------------------------')
    # print(request)
    # print('-------------------------')
    # tf.reset_default_graph()
    # requestdata = request.form["IMG_BASE64"]
    requestdata = request.json.get("IMG_BASE64")
    # print('---------------------')
    # print(request.json)
    # no_makeup = cv2.resize(imread(os.path.join('imgs', 'no_makeup', 'xzj_head.jpg')), (img_size, img_size))
    no_makeup = image.img_to_array(
        image.load_img(BytesIO(base64.b64decode(requestdata)),
                       target_size=(img_size, img_size)))  # / 255.
    # imgs/no_makeup/xzj_head.jpg
    X_img = np.expand_dims(pridictor.preprocess(no_makeup), 0)
    # makeups = glob.glob(os.path.join('imgs', 'makeup', '*.*')) #ref5.jpg is good
    # makeups = glob.glob(os.path.join('imgs', 'makeup', 'ref5.jpg'))  # ref5.jpg is good

    # ref5.jpg
    # makeup_bin = b"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"

    # ref2_f.jpg
    makeup_bin = b"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"

    # ref2_f_whited.jpg
    makeup_bin = b"/9j/4AAQSkZJRgABAQEAYABgAAD/4QCWRXhpZgAATU0AKgAAAAgABgExAAIAAAAwAAAAVgMBAAUAAAABAAAAhgMDAAEAAAABAAAAAFEQAAEAAAABAQAAAFERAAQAAAABAAAOxFESAAQAAAABAAAOxAAAAABtYXRwbG90bGliIHZlcnNpb24zLjIuMSwgaHR0cDovL21hdHBsb3RsaWIub3JnLwAAAYagAACxj//bAEMAAgEBAgEBAgICAgICAgIDBQMDAwMDBgQEAwUHBgcHBwYHBwgJCwkICAoIBwcKDQoKCwwMDAwHCQ4PDQwOCwwMDP/bAEMBAgICAwMDBgMDBgwIBwgMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDP/AABEIANUArgMBIgACEQEDEQH/xAAfAAABBQEBAQEBAQAAAAAAAAAAAQIDBAUGBwgJCgv/xAC1EAACAQMDAgQDBQUEBAAAAX0BAgMABBEFEiExQQYTUWEHInEUMoGRoQgjQrHBFVLR8CQzYnKCCQoWFxgZGiUmJygpKjQ1Njc4OTpDREVGR0hJSlNUVVZXWFlaY2RlZmdoaWpzdHV2d3h5eoOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4eLj5OXm5+jp6vHy8/T19vf4+fr/xAAfAQADAQEBAQEBAQEBAAAAAAAAAQIDBAUGBwgJCgv/xAC1EQACAQIEBAMEBwUEBAABAncAAQIDEQQFITEGEkFRB2FxEyIygQgUQpGhscEJIzNS8BVictEKFiQ04SXxFxgZGiYnKCkqNTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqCg4SFhoeIiYqSk5SVlpeYmZqio6Slpqeoqaqys7S1tre4ubrCw8TFxsfIycrS09TV1tfY2dri4+Tl5ufo6ery8/T19vf4+fr/2gAMAwEAAhEDEQA/AP2wib5Wz8rBu/eorlm5VQPrTLOb768kljTp59ke0ZbPoelfXctpHPKnZbkQYrC6t8zKT/KqGl3H2bTo9w2g561opKDG27dgKRWVqGoC20yPBVmxkYrWL6MxjRv7z0Rdm1GG3ttzSKOM4zk1lal4r+xwgr+7b+8e/wCFc/4o8Tw6HayTXLDgdOgzivlr9o39sG18H2sivfNbtu2ghyzN9B1pVKlOCM41L6QPorxb8dLHQ7ZluLtItrd3XAPtXlnjb9qfR7SKWSTV+eMKkgP581+evxj/AG0b66S4VJ7hSTkoxLMR/IfSvl/4q/td6hdu0hmkh2krjzD8/wCFeLiswik+R6nRSwrbTkj9CPit/wAFL9N8OXNxbQ3nlxuTtKoW+YHpketfOHxJ/wCCj1/rrSAXk1vCzlcb8SMPWvgbxX8ar7xJqLeZcXEob7pLHANYt58QZpfvMu4nHOSa82OaVUtTujhIrdH1/wCM/wBtG90/SpJpLq4kkl+WI+a2Cew61wOn/t7+JLS2ZWuW8xuGXzDwPSvme/8AFU2oLhrhmVDkA9Fqs3iBpo2+6dxwSwOR9K5njqr6lRowStY+tvCv7e/iCzRhcSXBjaXcmxycKfavXvh5/wAFFprS6hWW+k2gnAIO41+d9vr8kDBftE0fPY56V0uk+M1ktmVXy/O5Sfbr9aqnmFVO7D6pBp2R+ynwZ/b5TXbVGTVLcsy5CSSkNXvvgT9shpWC3FwGVgMEN/XFfg14a+IM+hiGaC6eJlIBUOeMelfRfwO/au1C1txGs7Xcce0vDI3zL+Nd+HzOUneTOeVBxVz90PAHx5j8RwW+25XdnDo4/lXp+heJYdQjjViA0n3T/Ca/I34J/teyJeQtHMqljkIW5j47V9l/Ar9rKHVhGtzN50R++f4ozxn6ivZp4qlJWvqc+IhKm9D7AI3yAFRuOakRPLXGKwfBvjCLxXYxSQzJ5hXKgdCtbSSbSu77x7VeoU5KUfMsxTNIhAC9c0+ONpQN2PUYqASeVJvU+uaspGxgXaR61lLTY0je5k2UO2R/95s05AWk/wBnOKhjuMyyjOPnPSm6jdC1WRvu7efpXXyu4SXOkyvq2px6cDGUZnYEHtXJX/iG30fQPPumEfBxluRVzWNWWJZJpJF3qPvP0A9a+UP2l/2hotH0W6tBP+7V33Sgjn3HtU1HyxuyZ0XJKKZxX7Zn7ZMumvJZ6fJlzmNByM/7Rr88/jF8anuL5ri6uPOlPUt8wXP1qh+01+0353iHUJrWSSSaQlI92Pu+uc18p+NPiZcaxqLIJGZZDlju6V87icdzvlfQ6qGF5VaOp13xL+N9xeJJb2bKJGJ85yeTXk9/qF5qN75kjN8ucb2qOaVoZX25cyHLEk9aqsvnhpA3Kn7tePOXNJux1RioaNkF7cyxuyhevACk5qWCH7YiqyBUXnJ61etYfNhkZsqFPBx1xTE0ppW3KC30NZuRqoykrp3MifT2tWZk+63GKjRPOHzMFVuntXSHRft0TK0fzIOucVlHQJPM/dxsvruojdohJvQzIg1vKy/6xQAQx6/StnTbT7a5ZVC/L0BwaemkTSJ+83fKeTiui8OaKwPzLt2r1K9RWftHflZXI46pmbBqe1Y9qsxU5G4YwenNdR4d8UXGmyxTW7xxyqRuQZyR6+9c1rtgxuWbafLUYGB0qrLetaqoAdSQOc9KfM/hKUJO0WfTfw4+Lk6m32kwSZ6OP9YP519YfAT46raQoy6hJFKrYLP8wA44x6V+ZmjeNZdMu4ssJBjGA3P4V7j8LPiPNCIWkuFU/ewD1HpXbha8+aKVjnrYd3uz9rP2bPj79kghKzrJBIN+0sSUPHT2Oa+vPB/iiHxTplvdI37xgMq3GBX44/sn/tDW95OLO4kWK6hHyrIcAk+lfoV+yh8ZP7dixG6NhdrRsew46V9dh6zqRfPueVGi4u6Pp6ebyV+YfeIqzDPhSGZV54HtXOXevW9/p6qqTD/bA6HvWVJqMjTnY7My8de1aezuioyV7HQsqrdyfLjc3BrN8V3/AJe2MMvy89ev1rSuWKSFu4PX0rifiJrLW1tdTAk7chTnqelOtPlhzG+G1Sb7Hlnx8+Ia6fC0C3C/Z41IfB6nv+Ffl9+278eWhS4s4Zl86d2L7WO2OIZ4x78V9iftbfGK38H+HNQnmdT9lQttz146E+/Svx5/aI+KE3irWdUv5pMfapTtQdAOwH06fhXhZhiXpCJ3U05S52ec/Efx9Pq99IdwcbsD6VyNnaozyNsO/PJ6mm3d+2oMW2sPm5zVzTLOS7m2hG/edcV4FSolqaq7naAz7MFnXqqv3NW4dDWZuANy9gc7vxrrvDXw1k1GVdqzYYBcbeleufDX9mJtWO6VCyn16iuStjlFWuddLL51ZJtHgtp4RuNRyiw5UjPQ1saX8KtQeWM7fkU/d719peDf2O0nhj324VZFH8BJb9K7i1/YrEU2UUbVUMNye1eT/aTloe9RyJpXSPhH/hUs8sZcLcfNwfl4qSD4GXV7EzKrtx3XpX6Dab+xLJNCJeGXGT8vA+gArodE/YqFvcrJiNVPXeh59c81k8wadrnZHIE90j88NB/Z7uriNo5oW2scgnj+lblx8DZrKx8vYvyc9ea+9L79mmCykljRI98Z+ZwvBHoKxNe+BEF1G2yFVGCM45qJYy7vcv8AsGEdUfnP4t8F3FqhXy/ukgnFcFruivCrq/zZyFb+79a++Pil+zM8kcn7pnXbkYHGBXzf8QfgxNpss6iJpIz/AAquP1ruw2Li3e5xYjK520R8+W9lJbTKyryv8ea6nw1q00TmN22qrZD/AIVBrPhiXSbryzvjRuBkdKpQ3jLBIkkjHa3OD1r1qdTm96J4NSnNScGfQnwf+Ld4mpQRrc/6RGy7WPcDtX6Hfsa/tCz6X4hsbmSZWWVlimyMqcnFfkV4J8W/ZNVt2ErMVbAHdea+y/2fPH86XNtKm7duUk7uvauyniJxsruxi8LGSsj9vvAvxHXXFgtxIJI5BuJ3fxEcYrotitIfvBvYV8y/syfEQa/4e08yH/SI0AVyeM9AM+uOa+ltI1KO70+OXcszMMErxX1+HrR5EluePUp8j5TqNVnW2MxMu3LEY9a8m+Neux6T4bkbzFVIyWYk8AV3ni/XI4fM3Mp2uzY9M180ftjeOY9J8HSuzKoZdwBJ2k4NTjqzjHl9DXLYJ0+aXY/Ov/gpJ8dftU66Fa3O4THz7gKfmIBO0Z985r89/G+utqmoNaL/AKlWIyTkjvXr37WHxCOt/EHULiWUsYZCqgccDNfPa37SXUkny/v2PU9Ca+UrSlKo2up006KcXYmMKSnbu+YAkH1r0r4Q/C2bWryKbaZFbnG3pXLfDbwfJ4j1eONY2ZugwO/rX23+zd8EVsrCOSaFvMIyRj2rw8ZiXTXKz28pwKnUUyx8HP2bvtFpC0kDSTseF2fdzX098N/2WodJto2MeFOMgj5q6j4DfDAQRRzSJtUcgYBz6V7roHg/zyrbT8vFfO1MRKbufcYfC04xtY4Dwl8J10uJVjTeBgYYdK7vRfhSJSu6FPm7ba7/AMN+Adrbmj69K7bSPCaxKPlGfWst/hPRioU1eZ5npnwojiUboU+U5AAFWrr4cK8RHkr8wxjHOK9Xi8OLGv3abN4fAH3acqTepP1yleyPBPEPwbheNljhVdwyWxXnXiv4RyacuFj2r1yBxX1jeeHFIO5Otcx4l8Ex3EDL5e5celTaUTb91U2PivxT4DEayKU38EYNeF/FP4GR6vuaKPaecjJr7p8c/DJYmkZU+9ntXjHjvwB5IbEeCc80U5zTbTOaph9PePzY+NfwJ+xTMqrtHOCAT39a+d/EPh7+x9SZW4OTgV+mnxZ+F8Oq20+2NVfHX0PWvjH46/DP+zp5CU/ewtwcAZr2sBipXt0PmMywEWnKKPnH+0ZtLumkWMqzH5ctX0l+y78Qp76KMeYPOj25BPQA/wCOK+dPFtnJbXe4ovyueB1rrvgB4lksddhmVgqNlWXrjnP9K95SUlc+XlGSkkfs3+xx41+2aFbr5jbnTzCpPRhx/KvtT4T679v0Uxl/9XzgmvzF/Yx8X+TeaVLuYiWYxsw+66tgYx+Nffnw28SNoIlKtmORB155/wA5r2MuxTU1Fnn4ynFPmZ3/AI7u50nkXf8A6w85HSviz/goz4+kt/BaQI4G5DkDjJwePrX2x4xu4biaSRowMtypb5a/PT/gpl4mtf7FKIsZjjidxg/dIzXrZhpGTZjhW407I/Jj42+IvO1zUN7ZZpWGc55rznS7nzp0ViOXXOe1bPxY1Jn1faMfvGMrEisLwncLe367BnnB4r5T2n2jootqLZ9RfsfeEG1XV/PaIOsZBBzX6JfAfwN9q2s0HzMdkY29u5r5K/Yc8CrFaW7NGdsnz5257D/69foz8C/CPkQxttVmUcHbjrivlMwqavzZ+gZNSkqSTPSvh/4QWyt4oY0+VeDxXrHhjwosaqSvJ6cVm+AvDSxxq23n6V6boWigKvy159NOTt0PcqVlRhd7kGkeHtnVf0rfstD2qBt/StDT9MVFHy1q29mAtepQopI+ZxWYykzH/skbagn0nC/drpvsP+zUFxa7e1dDoqRwxxjucndaVhelYupaSHVs1297aZU4rGv7Lhq5qtHTQ9bC4xnlXizwys6N8ufbFeO+OPCWPMXy/lb26V9H67Yb8153418PJcRtlfmNeVUjZ6H1NGo6sD49+J3gZrfzDHH1BznGDXyP+098PVispJjGFbALYxj61+iHxE8NKySKy8DPavmL9qDwBGPBlxdRw5k2kEe2OtFGTjNM4sVQ0Z+VXxm02Kxvm2jaOW49a4vwR4ik0LxhbybtsW4Iwz97Nei/tFWixX0v3lAY149YyEapBuDNhwK+zwknKJ+b5pUkq+h+oH7EusXL+GLdpGaSEzo8bA528jiv0j+GF/8A2z4aj2Rs2FXJJz6/41+Xn7AWvf8AFGrahvuujrk4I5OR+lfpV8BNVx4PXCsx74Nezgaf75X8zhruM6Tk9z2z4k3Men2c7K2ZNjEDB9K/Ln/go7rj6nbXiq38RjGc8DHP61+l/wAYLkPpmoNvxkEZ6ba/L79uTTJL/SLhwrOVZssP14r0swqP2du7OelRdtD8v/i2CuqsJOpGBjtUnwQ8ITeJPE1rCPmDOpPvzUvxpVrfW2ZlYoGIyBXtf/BOX4ZDx946jkaHd5TDkjOeeK+VxjdOn7p3YCjKpV5LdT9Cv2QvgzHpPhC0kkjRG8sbT6ivsb4T6RDp5jiUZwBzXnXw38CroGj2tqq/IqAA4xivWfB1hfXNysen2ny8L5j9Pyr5Cs5Te5+oYPDqEdOh7J4LdZVB4UdAPWvRNFhwi4w3rXh+l+DfHS2beTcWkMnO0kfKo+mKzdT134veDLouosryHGcAdPyrrwtSEVaaObHU/bu0WfUNr8i9BU8UwRq+a/DX7UPiqzuUh1nR/I+YhpAOMduK9e8G/E6PxZp8UpXy2bqPeu5Y6mnyngV8prxTk9V5Hfo+/vTZulZNrqoepZ9SwlbSqQ5eY8v6vJSsOviMdaxdSJIPHf1qv4g8WJplu8nDYrwf4k/tK65BfvBpdm8m3o23Ab161ySrx6HuYHLas1zLY9Y1pcq3zBQK4PxXeJGrfNuP0ry9Na+KfxAlYwvHYxtggkDp+daUfwa8bXFvuv8AWCZMZ2jkH2rgrU4t3PpMPejozF8fyKQzcNkHJFeL/FHw9D4j0O5t2K8xkAY68V6l4y+H3izw+kjfakvIVzuWVOR9CK871NZNSg3yRGG4jJEiHsaydKK2NpSUr3PyZ/bm+EEng/WboKhWNmJBI618rQiT+1VVeF3/AC89K/VH/goZ8Kv7Y8G3F/5bNJHkg46DGf6V+XdppUtz4ujtYxy02Gbp3zX0eW17qzex+f8AEGHVOamj7s/YL3201pG7Nu8jJHYnt/Ov0o+B+sNB4Y/dlm5x1r88v2KNCXRjZPMWEirgkdx2r9A/gqfN0Bh5jbR0wK+rwbbrRbPl5SvSZ798c7oLY3cbDPmEjPevg39p3wZcXHha8mWMSLkoFLYZifwr7y+N9hNMLk7dvkRl2z0+9/Ovj/8AaL1mSPwx5IUEMxbOOhrpzaTpw8ztyujGcVzn5EftX+HBo3iia2b5pEcHoR+FfXP/AARH+HLavdXV35fmfP8ALn2BNfPf7Zvha4uviLv+eRG53jkk96/Qj/gg18MceCL642jasmOnJGDXx2YVpex1PfyjD2xlux91eGvAIkuU8xcR4GPlr1jwhpsGmqkcca/KO4zmqtro/lH5V6cVyPxt+OFp8CvC82oXUMjmMZGB8o4Jyfyr5iNayPv5QTi4RPbrGVvJ7D2NN1Fg6fNtbPUEV+WWvftl/Gj9pnxBqUPhGabRdFsULm4kxH5mBnCADJ/HmvjrXP8AgqP8ZfBXiO4s7rx35E0Nw0BglR2CkEqCxGeuK66NOpWV/wAzwa1OnRlecvwP3i13TbeWc4jRvUHnI71N4ct47OQeSqx44IXivzn/AGEf+Ci3j7xZ4V0/VPHVm02i31wYFvkUsqvwBk9hX6JeENRj1q1huIjlZFDKQchgeQc1wSlPm5WrHr3UsPzRd0d5pUxZKm1C52Rmm6LalkHvRrUJSEnGOK9Hm9258u+V1bHI+IH88MG6Hiufi0a3ubwM0agKevr/AI1saznzG9Ca8P8A2kf2hrj4YNBo+h2cuqeI9QVntrSJdzBQOXbn5VHHJrypVWtWrn1mGjanZHvVhbw20W2MRxDkdhTdSk2R/LJux0+bivwq/aJ/4Km/GXQPihqGm3XiCHwzJHcmD7NFGZHiIJ+9nt9K6r9m79r34+fFLwRqHiCPxBb6pHpExWSNgVWdBz8hrunh6zhzWPPhWpSquPNdo/XXxnN5kUiyKrq3qM14p418LxyyyNGNoYkg15B+yv8At9TfF7/iU67b3llqSfI6zJ3z2foa+gp7UX0f7vDRyDINcfNOErM9mUYSgpRPlb9sTwG2qfCTUQF8xlibPOM8GvxW1mJtA+Isw2t8tweB161/Qn8Z/Ba618OdUt2jBUwP29jX4ZfFj4bMnxMv0gt90n2pyvHDYr2spqPV2PjeIMLzqN9j7b/ZetFv/DWj3CqwEkSs3qvHT9K+0/hCFsLI7YxIjRg8tjGa+N/2LNMmPgLT2mVlW32xsOuDzX2t4M1GCPTkji2xukaq/wAvPH/66+4yys6tTnZ8djMOqcND3v4xTy20OpbmG5gYzx1+bNfHXx7sm1nR/LWNd65JwPmwOtfX3x3UzxakysBsbLH0G7H518v/ABUszujbjarFTjqa7s4oTfM2TldeLskfFPxZ+CkfiXbcSQs00R2EFehr7l/4IteEo/DvgPXLfjcswPTnBB/wrz5vh5b65AyzKVByjDH3vevf/wDgnxo0fhTxFqloo/dzwqRj1UnP86/Psbd3TP0DLaN4+2R9Y2enbt2RnNZvjX4N6X8Q7Iw6lbrcKVxtdQV545FdNpMW563rbTg4rzIUU1dhWx06crpng9r+yD4c0Zp2tY5LWSQBR5TbVA9MdK+Zfi9/wQ0+HfxN8bS61Oz29xJIZmC8CQk5OQOvWv0Vl0NXHK1Wl8OqzfdyfpWqoyXwmX9pQqfxEn8j5P8AAH7Cul+Efh+3hK2um/sdRhIkhVfL4xwfWvevhT8Nl8A+FLLS45HuI7JPLR5Dlio6ZNdvH4fWMDCqMe1TQWXlt0NKFJ7yLr5pzQ9nBJIk0yDyI+cVB4iYGHt0/rVxRtWsvXn/AHZ6+tN6QZ5VG8qvMcneWnmudy/L296811D9nK1m+JV54s+3Xi6ldIIVGFaOOPAG0Aj1Gc16ovzyc8fWtK205ZkXI5rkw12fR/XHSPhX9oL/AII1fD/9oXx7N4i1J7i31C4bfI0PyrL9RXc/Cf8A4J3eGvg/8P8A/hHrHCafjBjjXbk9ySOST719cHw+rfwj8qik8Nrg8V3VI1FGybsYwxtFT51FXPmPR/2OfDvhu7jubexijlXo20b/AM66i58NrYxCNQ22MV7BqugLHH92uP8AEdiEibC9vSvLqU2tWe3h8XGrHlijxf4kbdO8Iak3byXGce1flV4g+DSeIPF19eGHbCs7MDjG41+qvxym+zeD7xfulo3x78V8g3Hw5SSwtfLjjaS4Yu5x0713YKWlkcmOpvl5ZEX7MvgyHS/D0cLR7RuLBCOuK9r8LXLRyyNGMKwxg+xrzzwY58OajCqD91Avlv3zmu80S5+zruQSMpGMgcGv0XIsLJK7PzHNaid4x6H1P47thqtnqMSru8wFvz/wNfM/jC3juVeOTzN8fXP94da+lNbv20/UbqPb5ynjKj+teDfEiyex1u4+Xcs5J2geo7V9NmVFTg2zx8vqezatscj4Zhji1dlZQ/2pfkB9fWvW/gBZL4c8ZLPtCtIpUY6c147Z7otQSNSf9HVm3egzwK9W8Aa+ty0NwJFWSOVUx/e461+W5pDkquyP0nh/GRnBwufWnh/UFn2svIYV1+lyq6V5d4H1XzrGFuPmUV6Fo12NleZh5cysx5rh7PQ6IICtO8hQKr214Cop098Aua7qVj5vllexDdbUFUJbwBqi1TVlRG56VirqhuJM52qD+dc8pR5rHp4fCycbs3VudwrI1+fbEe3FX7B/tIxntVDxRHttW9h1qatL3G0dGHilVUTmzqaifaTzzXSaDdCYKeuOtec6petFdNtbbjNbXgfxYty+1vlZW2kV5tCUYux9Djcvk6PPE9Pt4g6UT2qhOnWqmm6iroPmqa6vAV617keSUT4+UJKVjG15VCNXnni1gsTA122vXn3vmrznxzf7IG5/OvLxUUtD6zKKbWrPEPjfMLjSLhd3GwjmvGNQ0n7HZRlcLHEpAYdDxXrHxR1VDE6yEMJDtx615H448SrbQm1VW8xRnGe1b5bTdR8sF1NM3xUaMb3OT1SdXvJGjxuBPCn06Guu0LVFn02Jm37tuPlPFefyys8zSk7W/u4zWt4e1ptORo+sfUKRyDX6pl9F0oKLPyPMaqlJyPt7VTJczXLthFZz8o7gV5z8RvD39pRyPCrbox8pHU+1d3r+oNcXJ8po12k7h3BrntVjMlorM3yZr2a27XmebG9rHzz49W78PWrSMvk+bhQB1JByam0/4mLpNhZzTblaMjc0YzuHp9a674yaYNT0Tb5akwyb92OQBXBX+ibNNjVVaSO4xscj5Rxmvn84y2lWp3WjPeyvMJ4d2ifZ/wAJPEK6r4Zs5tw+ZARg9jXp+i6mQijdXzl+zZrrnwrbwy/6yIBW5/z7V7lol3uRTmvyuV6dRxP1CrFV6EandHdWuo7U+9xRc6kzL1rHtbrclSeYX710RqXPB+rJSuVdZuGlgbH3sjjNc9rXjGx8LaW15eTpDbxjLO7Y2iuqe1EoNcl46+EeneNUxdKzDjK7vlP4VjO97o9TBzo35KuiJvBPxq0PxlZyTaRqNrexxkqzROG2n3FSeJviHbxWEkkko8uNTuboAB61yUPwP03w8C+lwR6fNk8wjAc+4rGvvhhqWttJHqWoeZbMxYxouzcOwz6Vm5S2vY9Cng8K5c8WUbH47eHfGeuTWdlfQzXELFWGCuG9Peum8Mytda0Wjb93GvJB4JNcnF8ArC11MXEcMcJXvEdpI/z3rvfD2mR6TAsMa7VX1NcvL71z1pSjGlZPc7nSNSaOJfoKsXGrHZ1rnra5KjG6luNQKpXfCpZXPmZYNOd0Guajujb/ABry/wCIWrYhYA/rXYeIdT2wt83SvK/iBqDPFI27oK46k3Nnt4an7OFjxH4z+K2sYN8XzSLJnHWvHbrWrq5uJLqdlMjNjBGK7L4z3K3WqwIku1lJkK7vvDOP55rk9St45NIhxt3b8uM8ivu+G8LD2ftFufnnFGKl7Tl6ETTNforL8rY+bjFW7P8AdorOzcg9P60aJpEt+2FVWXI5J6V0Fr4X80NvbdtOMLyB+NfZyZ8XLs2fWGr7XmkbjI6EevNVtagaHTVXrz0x9Ke7+fqEiMpHzHPHWp/Eg22cZCfxetejU+I54fDc838Zxie2m3fKNu3iuRtdPhubGOzkkaQMhZD2B9K7vW4w93JFIvy8gkHtXI2Oix3kKRiQKWJVSDypHoK4a9NS0NY1UnpudJ8BtUbRdeksWkVt2PlDZxX0r4fud0K18gWept4T8UwsrP5iHOSdpcCvqD4beIF1vQLe5jOVkUMK/Ks8wro4nmS0ufq/DuI9pg1Te6PQLWf5Pwqyt9isq3uMx/hUOo30ltZvJGNzKDxivGlPTmO76vzSsdFb3pfkbTUksu9e34V8reNfjt8WPBeq3Ug8L2c2m72EM0c2XI7EjGOleVeKf2wPiRqtx5Bs9UiVT85gUdu3ygVP1i6ukenhOGa2Id6bVj7tvJl5ww78ZFZlzdKFbdtBxXwC37VHiqyuGkkbXI5P9p5D+hNUfE37YviLxMqqbrUAsIO9E3Ln64rF4pv7B9HR4JrreaPv550kXKkYFQ/avL9APWvzx0j9pvxet5JJZnXEXO4cttP4Guo0X9qT4o69qX9n6fardyOAS12QoA6dhipjzS1tYzxGQVaN7u9j7mj1YN91t30NOlvfMWvIfgNN4wisdviqSze4cbs253Lz05r01bjCd81PtJLS548qKTKPiK4/dN+Zry74g3Sw6dcTM21VGCfSvQPEN5vUqD83Ir5z/bL+LUfw/wDA0sMb4ur4GOMD9a3w8HOaikKvJUqbmzw3VfHsfi/xvetbMjeS3kqGI6A9qdqkoNz8qMuRztryXw3dzX14l1b7o2PzEjj3Nev+HdIutVsreb5900fLEcGv1HJMO6VFJ9T8bzasquIbL3g/baTsJPMdpCu1VPevR5bWFbSLbhSRk4Fc34V8Jx6fcrJMPOfA+Ufw11ETeazAZVV4x6V7knc8iUNT6S1HT4IL2VlX5zIQc9uap6qimzkLN0HpWrqVt9mWaX+LzOR3rD1K783TW+VhvPU+1enUXK7M54aQSOM1yMLcFifvqQxrltJuDpVw7xLG0kZwAw9a6fxOzSqy/eZl4x3rHjg/s1C0gX1Hcmkqbej1CUktzz/4tXP9nWcl05ZZcHAB53eldp+wr+0X/bkM3h/Um23Vux8oseWHpXF/FuytrjR555Bg8k7mr508C+J5/Cnxgh1Rbz7DbRy4G084FfA8UUqcpNR6H2HDuOqQqLsfrXY3g453K3SriJ5gwK8f+DXxrsfHGjQBbpJJ9oJII5r1PS9TEo+9+Nfn7k4vkZ+kSSlHniGveHodStXikRWDDGcV5Nq/wkk0K5drZFkRjkqy8ivcIdsqdBUN/oq3KH5Rn3qOVrSJ15fnFTCystj531CxtFk8u4soo5B/CYu1Yd3pOk2SySixtWkdgP8AV19Aa38PYtQILxqzL04rFl+F0O4M0KfKQR8vSnL2jVj6/D8SUuX/AIJ87nwLdeK9QaOGzFrbgkh9o+bmvSPhp8HLXwsPMeMPMw+8V5NejReDktAMIo28dKuJpi26/wBa55c63OXH51Ku7xKlhaeRGPl2+1LqF/8AZom56e9Lf3gtkPPSuW13Xo03M7bVXn61motr3TxW+rKfi/xTDpGnTXVw6xqiklmOAoH/AOqvzh/aN+PEfx0+KtzHb3TGy09/LiUnCnrz+Net/wDBQH9q1NMsZPDOj3TfaLgf6S6MMIndPqa+A/hP4ieHV7/zjJKLqchix+ZfcV9BlGHtJOW583nOLaTp3PpXwhZXFlBJuTEJOVI9a95+GURGhwR+Yy7k4z1FfKng74j3+iXQtS/mQscLvOQa98+F3xUF7bNDMm24h64Hy/ga/UMIl7Kx+VZhaFR26nr1mWi/dt/rM/eFWpotoH3vwrDTxHDdxqPOCyKoIBGd1bWnzecDuZW4raUmldHC5N6s+oPF9u0YkIbb1auV1S4MccKs2Q3r2zXRa2zX8uXkVfL6jua5LxBqlvaXm24aNbcZDEnGMCvTtOeqMr8sVcpalpXnWnmscrGcDJ61wfxA8Spp9z5cahQxwwI+b8Km8dfF630nTJFs2by4RuLN916+W/iH8Y9Q1rXrr7LN5e45DAgY9awxWJVOPKnqaYHB1K9Xma0R3Hxy+IUejeF57PzFluLoblA/gHua+d1kkvIVu2kaTd3HY5rpvFJfVI9rbpGkxiQ9qzdHtVawe1YfvIzknb1FfD5pUXXc+swqtU5V0Pbv2e/Fd3oN/a+S77GjDg5xtI6/yr66+FHxuXUpI4b6RY2YAZJ618ffCjT57Sxhm2n93Hjb0r1DSZW8hZkzHKpB47GvjMVBOWrPssDVcYpM+3dH1FZo1ZWDxsAQQa2reVZl6ivmL4Y/Hm60AQ2t1++hPy85+Svb9A8f2WswRyW9xGSwyV3ciuajpqehWw/PrE7KSJTjpVO4toyDz+dZ7+IRt+8tU7jxH82PWur2itqZUsLVuTXsKisLVb1YlbH8NM1zxbDZxNukVWHOCRmvKviJ8bbewtnWFvMkyR+FcdWV5e6erRjyfEbXjbxxDpEEjSSKOOADXz58XvjDqGoJJDZSMiuNu5T93PHpVbxL4xvvFl5IzNIsLcjnrzXLa7CTbsq8elZU73sY1Kx8n/HzQbmPXmaWb7TJMSzNndn868n8HWH2PWL5dudpIznoa+jPjrokbFpZFYshwrZ7+leIHwxcaXdyHbu86TggdjX1OVy5krnx2bRaqXJ/CWobpJreY+Y0cg2k8Fa9X+H+qSPGyyN5Uyr8p3Yye1ePafb/AGbXCzMq+YcOO/FelaBqIvpTtZfNt0G3H/LQe3vX29GXL6HhYrBqovdWp6tp/j+QxRLNHiRQASrE/wBa6zQfjGlqjHzpOmPnQY/A14zBrrQGPcS64H8PKn610Fnq1qYfnYK3oePWvQqe9T0Pl6lGUJctz9CvGnjWe3gZ40288DOe30rxH4keM7xjJcTN50kjY64VfoKKK9laU212OaMU6iTPJfGPiC68U3qx3EmIo487FGAea8p1Bs+JrpV+VYzgD8aKK+ZxUm56n1mBhGNJuJrTsZ7+3P8As9D0OKu+FtJjv/G1nDxHHJu3ADrjBoor5nOC8G25O59C6ToEOn+X5QVQ4GQBWksC2mqSQbVZZF3ZxjHSiivlcSlytn2VHSES3arv3K3zbTgHuKt2/iW88Oxq0MzbhnmiivNR7lCT5TotO+OWsWSLHmN8gHLdqdqXx61YRn5I+hHB/wDrUUUHZGTscLrvxX1XWJ5EaVkEhxwx4zWHczPdtudmZpCFYk5ziiih7kw1vcmtLVZoE7bhnH15qr4m02OK2+XqO9FFTI45Hz38dUM+oW8bkGPzMMAPvcE/+y/rXnWowL/bsSj7hIO08joaKK+oyX+Gj5bMJNu7Oe8W+H4rOUzR4X99jG32zUOjXslteSQhmJUh1fuvt9OaKK+w5nynkUv4r+R6ZY2q6po6SthJIwSxA+/j2qzZwfaJHSRmYKBj/P40UV6lB+4jwcckqzsf/9k="
    # makeup = image.load_img(BytesIO(base64.b64decode(makeup_bin)))
    try:
        #     for i in range(len(makeups)):
        # makeup = cv2.resize(imread(makeups[i]), (img_size, img_size))
        makeup = image.img_to_array(
            image.load_img(BytesIO(base64.b64decode(makeup_bin)), target_size=(img_size, img_size)))
        #         makeup = cv2.resize((makeup), (img_size, img_size))
        Y_img = np.expand_dims(pridictor.preprocess(makeup), 0)
        Xs_ = pridictor.predict(X_img, Y_img)
        Xs_ = pridictor.deprocess(Xs_)
    except:
        # print(makeups[i])
        pass
    buffer = Xs_[0]
    tmpfilename = uuid.uuid4().hex[:16] + '.jpg'
    image.save_img(os.path.join('imgs', 'log', tmpfilename), buffer)
    with open(os.path.join('imgs', 'log', tmpfilename), "rb") as imageFile:
        b64_image = base64.b64encode(imageFile.read())
    results = {"IMAGE": b64_image.decode()}

    ret = {"predictions": results}
    return Response(json.dumps(ret, ensure_ascii=False),
                    mimetype='application/json')
    # return jsonify(retdict)


# @app.route('/kitchen', methods=['POST'])
# def kitchen():
#     def cvDrawBoxes_voc(detections, img):
#         for detection in detections:
#             xmin, ymin, xmax, ymax = int(round(detection[0])), \
#                                      int(round(detection[1])), \
#                                      int(round(detection[2])), \
#                                      int(round(detection[3]))
#             pt1 = (xmin, ymin)
#             pt2 = (xmax, ymax)
#             cv2.rectangle(img, pt1, pt2, (255, 0, 0), 1)
#         return img
#
#     requestdata = request.json.get("IMG_BASE64")
#     score_thres = request.json.get("SCORE_THRES", 0.7)
#     img_back = request.json.get("IMG_BACK", False)
#     # print(img_back,type(img_back))
#     kittchen_pri.setscore_thres(score_thres)
#     kitchen_img = image.img_to_array(image.load_img(BytesIO(base64.b64decode(requestdata))), dtype=np.uint8)  # / 255.
#
#     Errors = 0
#     instance = None
#     b64_image = ''
#     items = []
#     try:
#         instance = kittchen_pri.predict(kitchen_img)["instances"].to("cpu")
#         fields = instance.get_fields()
#         pred_boxes = fields['pred_boxes'].tensor
#         # tensor([[689.5883, 137.1050, 741.8900, 204.3504],
#         #         [771.8320, 347.6593, 831.1061, 430.0320],
#         #         [410.0026, 112.5835, 446.0362, 148.0508],
#         #         [770.3798, 404.8280, 808.1330, 456.0722]])
#         scores = fields['scores']  # tensor([0.9970, 0.9778, 0.9586, 0.9293])
#         pred_classes = fields['pred_classes']  # tensor([3, 3, 3, 1])
#         if not img_back:
#             labels = kittchen_pri._create_text_labels(pred_classes, scores)
#         else:
#             labels = list(['face-head', 'mask-head', 'face-cap', 'mask-cap'][x] for x in pred_classes.numpy())
#         for i in range(len(instance)):
#             if kittchen_pri.score_thres <= scores[i].item():
#                 items.append(
#                     dict(zip(['box', 'class', 'score'], [pred_boxes[i].tolist(), labels[i], scores[i].item()])))
#         if img_back:
#             vlz = myx_Visualizer(kitchen_img, kittchen_pri.get_metadata(), instance_mode=1)
#             vout = vlz.draw_instance_predictions(predictions=instance)
#             back_img = vout.get_image()
#         else:
#             back_img = np.empty((2, 2, 3))
#         with tempfile.TemporaryDirectory() as tmpdirname:
#             cv2.imwrite(tmpdirname + 'xx.jpg', back_img)
#             with open(tmpdirname + 'xx.jpg', "rb") as imageFile:
#                 b64_image = base64.b64encode(imageFile.read())
#     except:
#         Errors = 1
#         raise
#     ret = {"predictions":
#         {
#             "Nums": len(items) if not Errors else 0,
#             "Items": items,
#             "Errors": Errors,
#             "IMG_BACK": b64_image.decode('utf-8'),
#         }
#     }
#     return Response(json.dumps(ret, ensure_ascii=False), mimetype='application/json')

@app.route('/kitchen', methods=['POST'])
def kitchen():
    def cvDrawBoxes_voc(detections, img):
        for detection in detections:
            xmin, ymin, xmax, ymax = int(round(detection[0])), \
                                     int(round(detection[1])), \
                                     int(round(detection[2])), \
                                     int(round(detection[3]))
            pt1 = (xmin, ymin)
            pt2 = (xmax, ymax)
            cv2.rectangle(img, pt1, pt2, (255, 0, 0), 1)
        return img

    requestdata = request.json.get("IMG_BASE64")
    score_thres = request.json.get("SCORE_THRES", 0.7)
    img_back = request.json.get("IMG_BACK", False)
    # print(img_back,type(img_back))
    # kittchen_pri.setscore_thres(score_thres)
    # kitchen_img = image.img_to_array(image.load_img(BytesIO(base64.b64decode(requestdata))), dtype=np.uint8)  # / 255.
    kitchen_img = base64toImageArray(requestdata)
    t_s = kitchen_img.shape[:2]
    o_s = yoyo.getsize()
    cv2.imwrite('xxxx.jpg', kitchen_img)
    thing_classes = ['face-head', 'mask-head', 'face-cap', 'mask-cap', 'uniform', 'non-uniform']
    Errors = 0
    # instance = None
    b64_image = ''
    items = []
    try:
        # instance = kittchen_pri.predict(kitchen_img)["instances"].to("cpu")
        predicts_ori, kitchen_img_resized = yoyo.darkdetect(kitchen_img)
        predicts = []
        for xxx in predicts_ori:
            if 'uniform' not in xxx[0]:
                predicts.append(xxx)
        predicts = kill_duplicate_by_score(predicts, xou_thres=.85)
        # ('uniform', 0.9847872257232666, (226.92221069335938, 266.7281188964844, 87.1346435546875, 198.78860473632812))
        # fields = instance.get_fields()
        # pred_boxes = fields['pred_boxes'].tensor
        # tensor([[689.5883, 137.1050, 741.8900, 204.3504],
        #         [771.8320, 347.6593, 831.1061, 430.0320],
        #         [410.0026, 112.5835, 446.0362, 148.0508],
        #         [770.3798, 404.8280, 808.1330, 456.0722]])
        # scores = fields['scores']  # tensor([0.9970, 0.9778, 0.9586, 0.9293])
        # pred_classes = fields['pred_classes']  # tensor([3, 3, 3, 1])
        # if not img_back:
        #     labels = _create_text_labels(predicts)
        # else:
        #     labels = list(thing_classes[x] for x in pred_classes.numpy())
        labels = _create_text_labels(predicts)
        for i in range(len(predicts)):
            # if kittchen_pri.score_thres <= scores[i].item():
            # print('===============')
            # print(predicts[i])#('mask-head', 0.9475332498550415, (250.86651611328125, 246.9287567138672, 66.5188980102539, 126.64704132080078))
            # print('===============')

            items.append(
                dict(zip(['box', 'class', 'score'],
                         [list(convertBackRatio(*convertBack(predicts[i][2]), o_s, t_s)), labels[i], predicts[i][1]])))
        if img_back:
            vlz = Visualizer(kitchen_img_resized, {"thing_classes": thing_classes}, instance_mode=1)
            instance = Instances(yoyo.getsize(),
                                 **{"pred_boxes": np.array(list(map(convertBack, [x[2] for x in predicts]))),
                                    "scores": np.array([x[1] for x in predicts]),
                                    "pred_classes": np.array([thing_classes.index(x[0]) for x in predicts])})
            vout = vlz.draw_instance_predictions(predictions=instance)
            back_img = vout.get_image()
        else:
            back_img = np.empty((2, 2, 3))
        with tempfile.TemporaryDirectory() as tmpdirname:
            cv2.imwrite(tmpdirname + 'xx.jpg', back_img)
            with open(tmpdirname + 'xx.jpg', "rb") as imageFile:
                b64_image = base64.b64encode(imageFile.read())
    except:
        Errors = 1
        raise
    ret = {"predictions":
        {
            "Nums": len(items) if not Errors else 0,
            "Items": items,
            "Errors": Errors,
            "IMG_BACK": b64_image.decode('utf-8'),
        }
    }
    return Response(json.dumps(ret, ensure_ascii=False), mimetype='application/json')


pridictor = beauty(output_saved_model_dir)
# kittchen_pri = kittchen(0.7)
yoyo = YOLO_single_img(configPath="cfg/chefCap.cfg", weightPath="cfg/chefCap_diounms_mosaic_20000.weights",
                       metaPath="cfg/chefCap.data", gpu_id=0)
app.run(debug=True, port=5123, host='10.1.251.211')

# FLASK_APP=api_server.py FLASK_ENV=development;python api_server.py
