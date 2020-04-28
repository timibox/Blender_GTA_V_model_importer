if "bpy" in locals():
    import importlib
    importlib.reload(file_parser)
else:
    from . import file_parser

import bpy
import os
import re

from mathutils import (Vector, Quaternion, Matrix, Euler)
from copy import deepcopy

bone_mapping = []
skel = None

def getNameFromFile(filepath):
    return os.path.basename(filepath)

opening_bracket = re.compile(r"\t+\{+")
closing_bracket = re.compile(r"\t+\}+")


def find_skel_file(mesh_path):
    def find_in_folder(folder):
        for file in os.listdir(folder):
            if file.endswith(".skel"):
                return os.path.join(folder, file)
        return None

    folder = os.path.dirname(os.path.abspath(mesh_path))
    search = find_in_folder(folder)
    if search:
        return search
    parent_folder = os.path.join(folder, os.pardir)
    search = find_in_folder(parent_folder)
    if search:
        return search
    return None

def load_skel(filepath):
    # skeleton pattern
    DataCRC_pattern = re.compile(r"\t+ DataCRC \s+ (?P<DataCRC>\d+)", re.VERBOSE)
    NumBones_pattern = re.compile(r"\t+ NumBones \s+ (?P<NumBones>\d+)", re.VERBOSE)
    Bone_header_pattern = re.compile(r"\t+ Bone \s+ (?P<bone_name>[^\s]+) \s+ (?P<bone_id>\d+)", re.VERBOSE)
    MirrorBoneId_pattern = re.compile(r"\t+ MirrorBoneId \s+ (?P<MirrorBoneId>\d+)", re.VERBOSE)
    Flags_pattern = re.compile(r"\t+ Flags \s+ (?P<flags>(([^\s]+)\s){1,6})", re.VERBOSE)
    RotationQuaternion_pattern = re.compile(r"\t+ RotationQuaternion (?P<RotationQuaternion>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){1,6})", re.VERBOSE)
    LocalOffset_pattern = re.compile(r"\t+ LocalOffset (?P<LocalOffset>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){1,6})", re.VERBOSE)
    Scale_pattern = re.compile(r"\t+ Scale (?P<Scale>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){1,6})", re.VERBOSE)
    Children_pattern = re.compile(r"\t+ Children \s+ (?P<Children>\d+)", re.VERBOSE)

    def getTransformFlags(flags):
        loc_rot = False
        loc_trans = False
        if "ROT_X" in flags and "ROT_Y" in flags and "ROT_Z" in flags:
            loc_rot = True
        if "TRANS_X" in flags and "TRANS_Y" in flags and "TRANS_Z" in flags:
            loc_trans = True
        return loc_rot, loc_trans

    def add_bone(lines, line_n, name, b_id, armature, obj, parent=None):
        global bone_mapping
        bone = {'id': b_id, 'name': name, 'children': {}}
        has_children = False
        line_number = line_n
        b_bone = 0
        loc_rot = False
        loc_trans = False
        while line_number < len(lines):
            line = lines[line_number]
            Flags_match = Flags_pattern.match(line)

            if Flags_match:
                loc_rot, loc_trans = getTransformFlags(Flags_match.group("flags"))

            RotQuat_match = RotationQuaternion_pattern.match(line)
            if RotQuat_match:
                bone["RotationQuaternion"] = tuple(float(r) for r in RotQuat_match.group("RotationQuaternion").split())
                line_number += 1
                continue

            LocOff_match = LocalOffset_pattern.match(line)
            if LocOff_match:
                bone["LocalOffset"] = tuple(float(l) for l in LocOff_match.group("LocalOffset").split())
                line_number += 1
                continue

            Scale_match = Scale_pattern.match(line)
            if Scale_match:
                bone_mapping.append(name)
                bone["Scale"] = tuple(float(s) for s in Scale_match.group("Scale").split())
                b_bone = armature.edit_bones.new(name)
                b_bone.head = (0,0,0)
                b_bone.tail = (0,0.05,0)
                b_bone.use_inherit_rotation = True
                b_bone.use_local_location = True
                quad = Quaternion((bone["RotationQuaternion"][3], bone["RotationQuaternion"][0], bone["RotationQuaternion"][1], bone["RotationQuaternion"][2]))
                mat = quad.to_matrix().to_4x4()
                b_bone.matrix = mat
                position = Vector(bone["LocalOffset"])
                b_bone.translate(position)
                if parent:
                    b_bone.parent = parent
                    b_bone.matrix = parent.matrix @ b_bone.matrix

                line_number += 1
                continue

            children_match = Children_pattern.match(line)
            if children_match:
                has_children = True
                line_number += 1
                continue


            bone_match = Bone_header_pattern.match(line)
            if bone_match:
                bone_id = bone_match.group("bone_id")
                bone_name = bone_match.group("bone_name")
                line_number += 1

                line_number, child = add_bone(lines, line_number, bone_name , bone_id, armature, obj, b_bone)
                bone["children"][bone_name] = child
                continue

            end_match = closing_bracket.match(line)
            if end_match:
                line_number += 2 if has_children else 1
                return line_number, bone

            line_number += 1

    skelett = {}
    num_bones = 0
    data_crc = 0
    arma = bpy.data.armatures.new(os.path.basename(filepath))
    Obj = bpy.data.objects.new(os.path.basename(filepath), arma)
    bpy.context.scene.collection.objects.link(Obj)
    bpy.context.view_layer.objects.active = Obj
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    with open(filepath, 'r') as file:
        lines = file.readlines()
        line_number = 0
        while line_number < len(lines):
        # for line in lines:
            line = lines[line_number]
            num_bones_match = NumBones_pattern.match(line)
            if num_bones_match:
                num_bones = int(num_bones_match.group("NumBones"))
                line_number += 1
                continue
            dat_match = DataCRC_pattern.match(line)
            if dat_match:
                data_crc = int(dat_match.group("DataCRC"))
                line_number += 1
                continue
            bone_match = Bone_header_pattern.match(line)
            if bone_match:
                bone_id = bone_match.group("bone_id")
                bone_name = bone_match.group("bone_name")
                line_number += 1
                line_number, skelett[bone_name] = add_bone(lines, line_number,bone_name, bone_id, arma, Obj)
                continue
            line_number += 1

    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    return Obj


vertexStructures = {
    "N209731BE": {"pos": 0, "normal": 1, "color": 2, "uv": 3},
    "N51263BB5": {"pos": 0, "normal": 1, "color": 2, "uv": 3, "undef3": 4},
    "S9445853F": {"pos": 0, "weights": 1, "bone_indices": 2, "normal": 3, "color": 4, "uv": 5, "undef3": 6},
    "S12D0183F": {"pos": 0, "weights": 1, "bone_indices": 2, "normal": 3, "color": 4, "undef1": 5, "uv": 6, "uv2": 7, "undef3": 8},
    "SD7D22350": {"pos": 0, "weights": 1, "bone_indices": 2, "normal": 3, "color": 4, "undef1": 5, "uv": 6, "undef3": 7},
    "SBED48839": {"pos": 0, "weights": 1, "bone_indices": 2, "normal": 3, "color": 4, "undef1": 5, "uv": 6},
    "NC794193B": {"pos": 0, "normal": 1, "color": 2, "bone_indices": 3, "uv": 4, "uv2": 5, "undef1": 5}
}

def load_Mesh(filepath):
    # re .mesh pattern
    global bone_mapping, skel
    index_header_pattern = re.compile(r"\s+ Indices \s+ (?P<index_count>\d+)", re.VERBOSE)
    index_line_pattern = re.compile(r"\t{4}(?P<indices>(?:\d+[^\.]){1,15})",re.VERBOSE)
    vertex_header_pattern = re.compile(r"\s+ Vertices \s+ (?P<vertex_count>\d+)", re.VERBOSE)
    skinned_pattern = re.compile(r"\t+ Skinned \s+ (?P<skinned>True|False)", re.VERBOSE)
    bone_count_pattern = re.compile(r"\t+ BoneCount \s+ (?P<bonecount>\d+)", re.VERBOSE)
    VertexDeclaration_pattern = re.compile(r"\s+ VertexDeclaration \s+ (?P<vertex_declaration>[^\s]+)", re.VERBOSE)

    # Todo add all VertexDeclarations
    vertex_line_patterns = {
        "N209731BE": r"""
            \t{4}
            (?P<pos>(?:(?:\s?[\-\+]?\d*(?:\.\d*)?)\s?){3}) \/
            (?P<normal>(?:(?:\s?[\-\+]?\d*(?:\.\d*)?)\s?){3}) \/
            (?P<color>(?:(?:\s?[\-\+]?\d*(?:\.\d*)?)\s?){4}) \/
            (?P<uv>(?:(?:\s?[\-\+]?\d*(?:\.\d*)?)\s?){2})$
            """,
        "N51263BB5": r"""
            \t{4}
            (?P<pos>(?:(?:\s?[\-\+]?\d*(?:\.\d*)?)\s?){3}) \/
            (?P<normal>(?:(?:\s?[\-\+]?\d*(?:\.\d*)?)\s?){3}) \/
            (?P<color>(?:(?:\s?[\-\+]?\d*(?:\.\d*)?)\s?){4}) \/
            (?P<uv>(?:(?:\s?[\-\+]?\d*(?:\.\d*)?)\s?){2}) \/
            (?P<undef3>(?:(?:\s?[\-\+]?\d*(?:\.\d*)?)\s?){4})$
            """,
        "S9445853F": r"""
            \t{4}
            (?P<pos>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){3}) \/\s
            (?P<weights>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){4}) \/\s
            (?P<bone_indices>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){4}) \/\s
            (?P<normal>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){3}) \/\s
            (?P<color>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){4}) \/\s
            (?P<uv>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){2}) (?:\/\s
            (?P<undef3>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){4}))?
            """,
        "S12D0183F": r"""
            \t{4}
            (?P<pos>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){3}) \/\s
            (?P<weights>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){4}) \/\s
            (?P<bone_indices>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){4}) \/\s
            (?P<normal>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){3}) \/\s
            (?P<color>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){4}) \/\s
            (?P<undef1>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){4}) \/\s
            (?P<uv>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){2}) \/\s
            (?P<uv2>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){2}) \/\s
            (?P<undef3>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){4})
            """,
        "SD7D22350": r"""
            \t{4}
            (?P<pos>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){3}) \/\s
            (?P<weights>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){4}) \/\s
            (?P<bone_indices>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){4}) \/\s
            (?P<normal>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){3}) \/\s
            (?P<color>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){4}) \/\s
            (?P<undef1>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){4}) \/\s
            (?P<uv>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){2}) \/\s
            (?P<undef3>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){4})
            """,
        "SBED48839": r"""
            \t{4}
            (?P<pos>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){3}) \/\s
            (?P<weights>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){4}) \/\s
            (?P<bone_indices>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){4}) \/\s
            (?P<normal>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){3}) \/\s
            (?P<color>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){4}) \/\s
            (?P<undef1>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){4}) \/\s
            (?P<uv>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s){2})
            """,
        "NC794193B": r"""
            \t{4}
            (?P<pos>(?:(?:\s?[\-\+]?\d*(?:\.\d*)?)\s?){3})\/\s
            (?P<normal>(?:(?:\s?[\-\+]?\d*(?:\.\d*)?)\s?){3})\/\s
            (?P<color>(?:(?:\s?[\-\+]?\d*(?:\.\d*)?)\s?){4}) \/\s
            (?P<bone_indices>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s?){4}) \/\s
            (?P<uv>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){2}) \/\s
            (?P<uv2>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s+){2}) \/\s
            (?P<undef1>(?:(?:[\-\+]?\d*(?:\.\d*)?)\s?){4})$
            """
    }


    Meshes = []
    Mesh = []
    Indices = []
    read_indices = False
    Vertices = []
    read_vertices = False


    skinned = False
    bone_count = 0
    weights = []
    index_counter = 0
    vertex_counter = 0
    v_line_pattern = 0



    with open(filepath, 'r') as file:
        for line in file.readlines():
            if not read_indices and not read_vertices:
                # find begining of index list
                index_header_match = index_header_pattern.match(line)
                if index_header_match:
                    read_indices = True
                    index_counter = 0
                    Mesh = []
                    Indices = []
                    continue

                # find beginning of vertex list
                vertex_header_match = vertex_header_pattern.match(line)
                if vertex_header_match:
                    read_vertices = True
                    vertex_counter = 0
                    Vertices = []
                    continue

                # get VertexDeclaration
                v_declaration_match = VertexDeclaration_pattern.match(line)
                if v_declaration_match:
                    declaration = v_declaration_match.group("vertex_declaration")
                    if declaration in vertex_line_patterns:
                        v_line_pattern = re.compile(vertex_line_patterns[declaration], re.VERBOSE)
                    else: # fallback for unknown declaration
                        v_line_pattern = re.compile(vertex_line_patterns["S9445853F"], re.VERBOSE)


                # get skinned
                skin_match = skinned_pattern.match(line)
                if skin_match:
                    skinned = skin_match.group("skinned") == "True"
                    continue

                # get bone count
                bone_match = bone_count_pattern.match(line)
                if bone_match:
                    bone_count = int(bone_match.group("bonecount"))
                    continue

            elif read_indices:
                # reading the indices
                index_match = index_line_pattern.match(line)
                if index_match and read_indices:
                    match_i = index_match.group("indices")
                    temp_list = list(int(i) for i in match_i.split())
                    Indices.extend(temp_list)
                    continue

                if closing_bracket.match(line):
                    read_indices = False
                    continue

            elif read_vertices:
                # read vertices
                if skinned:
                    vertex_match = v_line_pattern.match(line)
                    if vertex_match and read_vertices:
                        pos = Vector(float(p) for p in vertex_match.group("pos").split())
                        weights = Vector(float(p) for p in vertex_match.group("weights").split())
                        normal = Vector(float(p) for p in vertex_match.group("normal").split())
                        uv = Vector(float(p) for p in vertex_match.group("uv").split())
                        bone_indices = (int(p) for p in vertex_match.group("bone_indices").split())
                        uv[1] = 1.0 - uv[1]
                        Vertices.append((pos, normal, uv, weights, bone_indices))
                        vertex_counter += 1
                        continue
                else:
                    vertex_match = v_line_pattern.match(line)
                    if vertex_match and read_vertices:
                        pos = Vector(float(p) for p in vertex_match.group("pos").split())
                        normal = Vector(float(p) for p in vertex_match.group("normal").split())
                        uv = Vector(float(p) for p in vertex_match.group("uv").split())
                        uv[1] = 1.0 - uv[1]
                        Vertices.append((pos, normal, uv))
                        vertex_counter += 1
                        continue

                if closing_bracket.match(line):
                    read_vertices = False
                    Mesh.append(Indices)
                    Mesh.append(Vertices)
                    Meshes.append(Mesh)

    # create meshes
    base_name = getNameFromFile(filepath)
    for num, m in enumerate(Meshes):
        if m[1] and m[0]:
            name = base_name + str(num)
            # populate faces
            faces = [[m[0][i*3], m[0][i*3+1], m[0][i*3+2]] for i in range(int(len(m[0])/3))]

            mesh = bpy.data.meshes.new(name)
            verts = list(v[0] for v in m[1])
            mesh.from_pydata(verts, (), faces)

            if not mesh.validate():
                Obj = bpy.data.objects.new(name, mesh)
                # add uvs
                mesh.uv_layers.new(name="UVMap")
                uvlayer = mesh.uv_layers.active.data
                mesh.calc_loop_triangles()
                normals = []
                for i, lt in enumerate(mesh.loop_triangles):
                    for loop_index in lt.loops:
                        # set uv coordinates (2)
                        uvlayer[loop_index].uv = m[1][mesh.loops[loop_index].vertex_index][2]
                        # set normals (1)
                        normals.append(m[1][mesh.loops[loop_index].vertex_index][1])
                        # add bone weights
                        if skinned and skel:
                            # bone indices (4)
                            for i, vg in enumerate(m[1][mesh.loops[loop_index].vertex_index][4]):
                                vg_name = bone_mapping[vg]
                                if not vg_name in Obj.vertex_groups:
                                    group = Obj.vertex_groups.new(name=vg_name)
                                else:
                                    group = Obj.vertex_groups[vg_name]
                                # bone weights (3)
                                weight = m[1][mesh.loops[loop_index].vertex_index][3][i]
                                if weight > 0.0:
                                    group.add([mesh.loops[loop_index].vertex_index], weight, 'REPLACE' )


                # normal custom verts on each axis
                mesh.use_auto_smooth = True
                mesh.normals_split_custom_set(normals)

                mat = bpy.data.materials.new(name=name)
                mesh.materials.append(mat)
                bpy.context.scene.collection.objects.link(Obj)
                Obj.select_set(True)
                bpy.context.view_layer.objects.active = Obj
            else:
                print("mesh validation failed")
        else:
            print("missing vertex data")
    if bpy.context.view_layer.objects.active:
        bpy.ops.object.join()
        bpy.context.view_layer.objects.active.name = base_name
        return bpy.context.view_layer.objects.active
    else:
        return None

def find_skel_file(mesh_path):
    def find_in_folder(folder):
        for file in os.listdir(folder):
            if file.endswith(".skel"):
                return os.path.join(folder, file)
        return None

    folder = os.path.dirname(os.path.abspath(mesh_path))
    search = find_in_folder(folder)
    if search:
        return search
    parent_folder = os.path.join(folder, os.pardir)
    search = find_in_folder(parent_folder)
    if search:
        return search
    return None




# ─── REWORK ─────────────────────────────────────────────────────────────────────



def setVertexAttributes(Obj, mesh, VertexData, VertexDeclaration, skinned):
    mesh.uv_layers.new(name="UVMap")
    uvlayer = mesh.uv_layers.active.data
    mesh.calc_loop_triangles()
    normals = []

    # get vertex mapping
    normalIndex = vertexStructures[VertexDeclaration]["normal"]
    uvIndex = vertexStructures[VertexDeclaration]["uv"]
    if skinned:
        boneIndex = vertexStructures[VertexDeclaration]["bone_indices"]
        weightIndex = vertexStructures[VertexDeclaration]["weights"]

    for i, lt in enumerate(mesh.loop_triangles):
        for loop_index in lt.loops:
            # set uv coordinates
            uvlayer[loop_index].uv = VertexData[mesh.loops[loop_index].vertex_index][uvIndex]
            # flip y axis
            uvlayer[loop_index].uv[1] = 1 - uvlayer[loop_index].uv[1]
            # set normals (1)
            normals.append(VertexData[mesh.loops[loop_index].vertex_index][normalIndex])
            # add bone weights
            if skinned:
                # bone indices (4)
                for i, vg in enumerate(VertexData[mesh.loops[loop_index].vertex_index][boneIndex]):
                    vg_name = bone_mapping[int(vg)]
                    if not vg_name in Obj.vertex_groups:
                        group = Obj.vertex_groups.new(name=vg_name)
                    else:
                        group = Obj.vertex_groups[vg_name]
                    # bone weights (3)
                    weight = VertexData[mesh.loops[loop_index].vertex_index][weightIndex][i]
                    if weight > 0.0:
                        group.add([mesh.loops[loop_index].vertex_index], weight, 'REPLACE' )

    # normal custom verts
    mesh.use_auto_smooth = True
    mesh.normals_split_custom_set(normals)


def importMesh(filepath, skinned=False, **kwargs):
    p = file_parser.GTA_Parser()
    p.read_file(filepath)
    # p.print_blocks()
    base_name = getNameFromFile(filepath)

    for num, geometry in enumerate(p.data["members"][0]["members"][1]["members"]):
        name = base_name + str(num)
        faces = geometry["members"][0]["faces"]
        verts = geometry["members"][1]["positions"]
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, (), faces)

        if not mesh.validate():
            VertexDeclaration = geometry["VertexDeclaration"]
            Obj = bpy.data.objects.new(name, mesh)
            setVertexAttributes(Obj, mesh, geometry["members"][1]["vertices"], VertexDeclaration, skinned and p.data["members"][0]["Skinned"])
            bpy.context.scene.collection.objects.link(Obj)
            Obj.select_set(True)
            bpy.context.view_layer.objects.active = Obj

    if bpy.context.view_layer.objects.active:
        bpy.ops.object.join()
        bpy.context.view_layer.objects.active.name = base_name
        activeObject = bpy.context.view_layer.objects.active
        activeObject.select_set(False)
        return activeObject
    else:
        return None

def buildArmature(skel_file):
    arma = bpy.data.armatures.new(os.path.basename(skel_file.name))
    Obj = bpy.data.objects.new(os.path.basename(skel_file.name), arma)
    bpy.context.scene.collection.objects.link(Obj)
    bpy.context.view_layer.objects.active = Obj
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)

    numBones = skel_file.data["members"][0]["NumBones"]

    def addBone(bone, armature, obj, parent=None):
        global bone_mapping

        bone_name = bone["attributes"][0]
        bone_mapping.append(bone_name)
        b_bone = armature.edit_bones.new(bone_name)
        b_bone.head = (0,0,0)
        b_bone.tail = (0,0.05,0)
        b_bone.use_inherit_rotation = True
        b_bone.use_local_location = True
        quad = Quaternion((float(bone["RotationQuaternion"][3]), float(bone["RotationQuaternion"][0]),
            float(bone["RotationQuaternion"][1]), float(bone["RotationQuaternion"][2])))
        # quad = Quaternion(map(float, bone["RotationQuaternion"]))
        mat = quad.to_matrix().to_4x4()
        b_bone.matrix = mat
        position = Vector(map(float, bone["LocalOffset"]))
        b_bone.translate(position)
        if parent:
            b_bone.parent = parent
            b_bone.matrix = parent.matrix @ b_bone.matrix

        # add child bones
        for children in bone["members"]:
            for child in children["members"]:
                addBone(child, armature, obj, b_bone)

    addBone(skel_file.data["members"][0]["members"][0], arma, Obj)
    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    return Obj


def loadSkeleton(filepath, folder="", name="", **kwargs):
    skel_path = os.path.join(folder, name, name + ".skel")
    if not os.path.exists(skel_path):
        def find_in_folder(folder):
            for file in os.listdir(folder):
                if file.endswith(".skel"):
                    return os.path.join(folder, file)
            return None
        skel_path = find_in_folder(folder)
    skel_file = file_parser.GTA_Parser()
    if skel_file.read_file(skel_path):
        skel_file.print_blocks()
        return buildArmature(skel_file)
    else:
        print(skel_path)
        print("skel file not found")
        return None


def loadODR(filepath, **kwargs):
    odrFile = file_parser.GTA_Parser()
    odrFile.read_file(filepath)
    name = os.path.basename(filepath).split(".")[0]
    lodgroup = odrFile.getMemberByName("LodGroup")
    mesh_path = ""
    for key, value in lodgroup["members"][0].items():
        if name in key and key.endswith(".mesh"):
            mesh_path = os.path.join(kwargs["folder"], *key.split("\\"))
    return importMesh(mesh_path, **kwargs)

def loadODD(filepath, **kwargs):
    oddFile = file_parser.GTA_Parser()
    oddFile.read_file(filepath)
    root = oddFile.getMemberByName("Version")
    mesh_list = []
    base_path = kwargs["folder"]
    for odr in root["values"]:
        odr_path = os.path.join(base_path, *odr.split("\\"))
        kwargs["folder"] = os.path.dirname(odr_path)
        mesh_list.append(loadODR(odr_path, **kwargs))
    return mesh_list

def deselectAll():
    for obj in bpy.data.objects:
        obj.select_set(False)

def load(operator, context, filepath="", import_armature=True, **kwargs):
    def message(self, context):
        self.layout.label(text="failed to import model!")

    bpy.context.view_layer.objects.active = None

    deselectAll()
    skel = None
    if import_armature:
        skel = loadSkeleton(filepath, **kwargs)

    kwargs["skinned"] = bool(skel)

    if kwargs["file_extension"] == "odr":
        meshObjects = [loadODR(filepath, **kwargs)]
    if kwargs["file_extension"] == "odd":
        meshObjects = loadODD(filepath, **kwargs)


    if meshObjects:
        if skel:
            for mesh in meshObjects:
                mod = mesh.modifiers.new("armature", 'ARMATURE')
                mod.object = skel
                mesh.parent = skel
    else:
        bpy.context.window_manager.popup_menu(message, title="Error", icon='ERROR')
    return {'FINISHED'}