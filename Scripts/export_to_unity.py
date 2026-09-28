"""Working FBX exporter for Blender 3.6 LTS.
Usage: blender -b Sources/quality_sample.blend --python Scripts/export_to_unity.py -- --validate
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from blender_asset_pack_common import ROOT, DIRS, validate

def export_collection(col_name, out_name):
    col=bpy.data.collections.get(col_name)
    if not col: raise RuntimeError(f'Missing export collection: {col_name}')
    objects=[o for o in col.all_objects if o.type in {'MESH','ARMATURE','EMPTY'} and not o.name.startswith(('SHOWCASE_','REF_'))]
    if not objects: raise RuntimeError(f'Empty export collection: {col_name}')
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects: o.select_set(True)
    bpy.context.view_layer.objects.active=next((o for o in objects if o.type=='ARMATURE'),objects[0])
    out=DIRS['Characters']/out_name if col_name.startswith('Char') else DIRS['Equipment']/out_name if col_name.startswith('Equip') else DIRS['Environment']/out_name
    out.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=str(out),use_selection=True,object_types={'EMPTY','MESH','ARMATURE'},use_mesh_modifiers=True,add_leaf_bones=False,apply_unit_scale=True,axis_forward='-Z',axis_up='Y',bake_anim=True)
    if not out.exists() or out.stat().st_size==0: raise RuntimeError(f'Empty export: {out}')
    return str(out)

def main():
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []; do_validate='--validate' in argv
    exports=[]
    for col,name in [('Char_Officer','Officer_Quality.fbx'),('Equip_Carbine','Carbine_Quality.fbx'),('Env_QualityRoom','QualityRoom.fbx')]: exports.append(export_collection(col,name))
    if do_validate: validate(DIRS['Documentation']/'export_validation.json')
    print('EXPORTED',*exports,sep='\n')
if __name__=='__main__': main()
