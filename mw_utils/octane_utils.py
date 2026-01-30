import c4d
import maxon
import os
import re

# --- Octane Node IDs (from octane_id.py) ---
ID_OCT_VIDEO_POST = 1029525
ID_OCT_STANDARD_SURFACE = 1058763
ID_OCT_IMAGE_TEXTURE = 1029508
ID_OCT_RGBSPECTRUM = 1029504
ID_OCT_MULTIPLY_TEXTURE = 1029516
ID_OCT_MIXTEXTURE = 1029505
ID_OCT_COLORCORRECTION = 1029512
ID_OCT_INVERT_TEXTURE = 1029514
ID_OCT_DISPLACEMENT = 1031901
ID_OCT_FLOAT_TEXTURE = 1029506
ID_OCT_GRADIENT_TEXTURE = 1029513
ID_OCT_TRIPLANAR = 1038882 # Triplanar Texture (Newer)
ID_OCT_TRIPLANAR_PROJECTION = 1031300 # Triplanar Projection
ID_OCT_TRANSFORM = 1031301 # UV Transform

# --- Octane Port IDs (Inferred/Standard) ---
# Note: Octane ports are often accessed by Int ID, not String.
# We will define integer constants for known ports based on common knowledge and estimation.

# Standard Surface Ports
OCT_MAT_USE_COLOR = 2002            
OCT_MAT_DIFFUSE_LINK = 2003         
OCT_MAT_SPECULAR_LINK = 2006        
OCT_MAT_ROUGHNESS_LINK = 2007        
OCT_MAT_BUMP_LINK = 2008             
OCT_MAT_NORMAL_LINK = 2009           
OCT_MAT_OPACITY_LINK = 2011          
OCT_MAT_TRANSMISSION_LINK = 2010     
OCT_MAT_EMISSION_LINK = 2012         
OCT_MAT_DISPLACEMENT_LINK = 2013     

# Image Texture Ports
IMAGETEXTURE_FILE = 1000
IMAGETEXTURE_POWER = 1004
IMAGETEXTURE_GAMMA = 1005
IMAGETEXTURE_INVERT = 1006
IMAGETEXTURE_TYPE = 1012        # 0=Normal, 1=Float
IMAGETEXTURE_MODE = 1012 
IMAGETEXTURE_U_SCALE = 1007
IMAGETEXTURE_V_SCALE = 1008
IMAGETEXTURE_TRANSFORM_LINK = 1002 # transform link
IMAGETEXTURE_PROJECTION_LINK = 1003 # projection link


# Color Correction Ports
COLORCOR_TEXTURE_LNK = 1000
COLORCOR_BRIGHTNESS = 1001
COLORCOR_CONTRAST = 1002
COLORCOR_GAMMA = 1003
COLORCOR_HUE = 1004
COLORCOR_SATURATION = 1005

# Multiply Texture Ports
MULTIPLY_TEXTURE1 = 1000
MULTIPLY_TEXTURE2 = 1001

# Invert Texture Ports
INVERT_TEXTURE = 1000

# Mix Texture Ports
MIXTEX_AMOUNT = 1000
MIXTEX_TEXTURE1 = 1001
MIXTEX_TEXTURE2 = 1002

# Displacement Ports
DISPLACEMENT_AMOUNT = 1000
DISPLACEMENT_LEVELOFDETAIL = 1001
DISPLACEMENT_TEXTURE = 1003

# Transform Node Ports
TRANSFORM_SCALE = 1000 # Vector
TRANSFORM_ROTATION = 1002 # Vector (Angle?) check type
TRANSFORM_TRANSLATION = 1001 # Vector
# Note: Transform logic might be different (S/R/T might be floats or vectors depending on implementation)
# Looking at standard Octane Transform:
# 1000: Scale (Vector)
# 1001: Translation (Vector)
# 1002: Rotation (Vector, Euler)

# Triplanar Projection Ports
TRIPLANAR_PROJ_S_X = 1000
TRIPLANAR_PROJ_S_Y = 1001
TRIPLANAR_PROJ_S_Z = 1002
# Often Triplanar Projection just needs to be created, defaults are usually fine.


# Triplanar Ports
TRIPTEX_TEXTURE1 = 1000 # Input Texture

# --- Texture Channels (Reused from redshift_utils) ---
TEXTURE_CHANNELS = {
    "base_color":        ["basecolor", "base", "color", "albedo", "diffuse", "diff", "col", "bc", "alb", "rgb" , "d", "dif"],
    "normal":            ["normalgl", "normalopengl", "normal", "norm", "nrm", "nml", "nrml", "nor", "n"],
    "bump":              ["bump", "b"],
    "ao":                ["ao", "ambient", "occlusion", "occ", "amb", "ambientocclusion"],
    "metalness":         ["metallic", "metalness", "metal", "mtl", "met", "m"],
    "refl_roughness":    ["roughness", "rough", "rgh", "r"],
    "refl_weight":       ["specular", "spec", "s", "refl", "reflection"],
    "glossiness":        ["glossiness", "gloss", "g"],
    "opacity_color":     ["opacity", "opac", "alpha", "o", "a", "cutout"],
    "translucency":      ["translucency", "transmission", "trans", "sss", "subsurface", "scatter", "scattering"],
    "displacement":      ["displacement", "disp", "dsp", "height", "h"],
    "emission_color":    ["emissive", "emission", "emit", "illu", "illumination", "selfillum", "e"]
}

def _split_into_components(fname):
    """
    Split filename into components for channel detection.
    """
    fname = os.path.splitext(fname)[0]
    fname = "".join(i for i in fname if not i.isdigit())
    separators = [" ", ".", "-", "__", "--", "#"]
    for sep in separators:
        fname = fname.replace(sep, "_")
    components = fname.split("_")
    components = [c.lower() for c in components if c.strip()]
    return components

def GetTextureChannel(fname):
    """
    Determines the texture channel by analyzing filename components.
    """
    components = _split_into_components(fname)
    for component in reversed(components):
        for channel, keywords in TEXTURE_CHANNELS.items():
            if component in keywords:
                return channel
    return None

# --- Helper Functions (Ported from OctaneHelper) ---

def CreateOctaneMaterial(doc=None, name="Octane Standard Surface"):
    if not doc:
        doc = c4d.documents.GetActiveDocument()
    
    mat = c4d.BaseMaterial(ID_OCT_STANDARD_SURFACE)
    mat.SetName(name)
    doc.InsertMaterial(mat)
    return mat

def AddShaderToMaterial(material, shader):
    """
    Helper to insert shader into material's shader tree.
    """
    material.InsertShader(shader)

def AddImageTexture(material, texture_path, node_name=None, is_float=False, gamma=2.2, invert=False):
    """
    Creates and sets up an Octane Image Texture Shader.
    Does NOT connect it to any material port.
    """
    tex_node = c4d.BaseList2D(ID_OCT_IMAGE_TEXTURE)
    AddShaderToMaterial(material, tex_node)
    
    if texture_path:
        tex_node[IMAGETEXTURE_FILE] = texture_path
    
    tex_node[IMAGETEXTURE_INVERT] = invert
    tex_node[IMAGETEXTURE_GAMMA] = gamma
    
    if is_float:
        tex_node[IMAGETEXTURE_MODE] = 1 # Float
        # Usually Float textures use Gamma 1.0, but user override is respected
        if gamma == 2.2: # If default was passed but it's float, maybe force 1.0? 
            tex_node[IMAGETEXTURE_GAMMA] = 1.0
    else:
        tex_node[IMAGETEXTURE_MODE] = 0 # Normal (Color)
        
    if node_name:
        tex_node.SetName(node_name)
    else:
        tex_node.SetName(os.path.basename(texture_path))

    return tex_node

def AddCC(material, input_shader, parent_node=None):
    """
    Adds a Color Correction shader to the input shader.
    """
    cc_node = c4d.BaseList2D(ID_OCT_COLORCORRECTION)
    AddShaderToMaterial(material, cc_node)
    
    if input_shader:
        cc_node[COLORCOR_TEXTURE_LNK] = input_shader
        
    return cc_node

def AddMultiply(material, shader1, shader2):
    """
    Adds a Multiply shader combining two shaders.
    """
    mul_node = c4d.BaseList2D(ID_OCT_MULTIPLY_TEXTURE)
    AddShaderToMaterial(material, mul_node)
    
    if shader1:
        mul_node[MULTIPLY_TEXTURE1] = shader1
    if shader2:
        mul_node[MULTIPLY_TEXTURE2] = shader2
        
    return mul_node

def AddDisplacement(material):
    disp_node = c4d.BaseList2D(ID_OCT_DISPLACEMENT)
    AddShaderToMaterial(material, disp_node)
    return disp_node

def SetupTextures(material, tex_data):
    """
    Orchestrates the creation and connection of PBR textures.
    Adapted from OctaneHelper logic.
    """
    try:
        # 1. Diffuse (Base Color) + AO
        if "base_color" in tex_data:
            path = tex_data["base_color"]
            albedo_node = AddImageTexture(material, path, node_name="Albedo", is_float=False, gamma=2.2)
            
            final_diffuse = albedo_node
            # If AO exists, multiply it
            if "ao" in tex_data:
                ao_path = tex_data["ao"]
                ao_node = AddImageTexture(material, ao_path, node_name="AO", is_float=True, gamma=1.0)
                # Usually AO is multiplied with Diffuse
                # But sometimes users want separate AO. Here we follow standard PBR multiply.
                # However, Octane Standard Surface doesn't have dedicated AO slot commonly used like RS.
                # We will multiply albedo with AO.
                cc_albedo = AddCC(material, albedo_node) # CC is often added for control
                final_diffuse = AddMultiply(material, cc_albedo, ao_node)
            
            material[OCT_MAT_DIFFUSE_LINK] = final_diffuse

        # 2. Roughness / Glossiness
        if "refl_roughness" in tex_data:
            path = tex_data["refl_roughness"]
            rough_node = AddImageTexture(material, path, node_name="Roughness", is_float=True, gamma=1.0)
            cc_rough = AddCC(material, rough_node)
            material[OCT_MAT_ROUGHNESS_LINK] = cc_rough
            
        elif "glossiness" in tex_data:
            path = tex_data["glossiness"]
            gloss_node = AddImageTexture(material, path, node_name="Glossiness", is_float=True, gamma=1.0)
            cc_gloss = AddCC(material, gloss_node)
            # Invert for roughness? Octane usually expects Roughness. 
            # If glossiness, might need Invert node or just CC invert.
            # For now, link to Roughness (Standard Surface behaves as Roughness usually)
            # Check if we need to invert.
             # material[OCT_MAT_ROUGHNESS_LINK] = cc_gloss 
             # We might need to invert it manualy in CC or Invert Node.
            
            # Let's add Invert Node
            inv_node = c4d.BaseList2D(ID_OCT_INVERT_TEXTURE)
            AddShaderToMaterial(material, inv_node)
            inv_node[INVERT_TEXTURE] = cc_gloss
            material[OCT_MAT_ROUGHNESS_LINK] = inv_node

        # 3. Metalness / Specular
        if "metalness" in tex_data:
             path = tex_data["metalness"]
             metal_node = AddImageTexture(material, path, node_name="Metalness", is_float=True, gamma=1.0)
             material[OCT_MAT_SPECULAR_LINK] = metal_node # Link to Specular/Metallic slot
             material[OCT_MAT_USE_COLOR] = 0 # Often need to disable diffuse color usage for pure metal workflow?
             # Actually Standard Surface has Metallic float, but if using map, link to Specular usually works if Metallic mode is on.
             # IMPORTANT: Octane Standard Surface has "Metallic" float channel (ID 2004?) and "Specular" link (2006).
             # Usually linking to Specular Link (2006) drives the metallicity if the material type is Universal or Metallic?
             # But here we are using Standard Surface (1058763).
             # Let's assume linking to Specular Link is correct for now.

        elif "refl_weight" in tex_data: # Specular Map
             path = tex_data["refl_weight"]
             spec_node = AddImageTexture(material, path, node_name="Specular", is_float=False, gamma=2.2)
             material[OCT_MAT_SPECULAR_LINK] = spec_node

        # 4. Normal
        if "normal" in tex_data:
            path = tex_data["normal"]
            norm_node = AddImageTexture(material, path, node_name="Normal", is_float=False, gamma=1.0) # Normal is usually non-color data
            material[OCT_MAT_NORMAL_LINK] = norm_node

        # 5. Bump
        if "bump" in tex_data:
             path = tex_data["bump"]
             bump_node = AddImageTexture(material, path, node_name="Bump", is_float=True, gamma=1.0)
             material[OCT_MAT_BUMP_LINK] = bump_node
        
        # 6. Displacement
        if "displacement" in tex_data:
             path = tex_data["displacement"]
             disp_tex_node = AddImageTexture(material, path, node_name="Displacement", is_float=True, gamma=1.0)
             
             disp_node = AddDisplacement(material)
             disp_node[DISPLACEMENT_TEXTURE] = disp_tex_node
             disp_node[DISPLACEMENT_LEVELOFDETAIL] = 11 # 2k resolution default
             disp_node[DISPLACEMENT_AMOUNT] = 10.0 # Default amount
             
             material[OCT_MAT_DISPLACEMENT_LINK] = disp_node

        # 7. Opacity / Alpha
        if "opacity_color" in tex_data:
             path = tex_data["opacity_color"]
             alpha_node = AddImageTexture(material, path, node_name="Opacity", is_float=True, gamma=1.0)
             material[OCT_MAT_OPACITY_LINK] = alpha_node

        # 8. Emission
        if "emission_color" in tex_data:
              path = tex_data["emission_color"]
              emit_tex_node = AddImageTexture(material, path, node_name="Emission", is_float=False, gamma=2.2)
              
              # Octane Emission usually requires Texture Emission or Blackbody Emission node linked to Emission Link
              # But Standard Surface might have direct link.
              # Let's use Texture Emission Node for robustness if needed, 
              # OR check if Standard Surface Emission Link accepts Image Texture directly.
              # Usually calls for "Texture Emission" (ID 1029642).
              ID_OCT_TEXTURE_EMISSION = 1029642
              tex_emit_node = c4d.BaseList2D(ID_OCT_TEXTURE_EMISSION)
              AddShaderToMaterial(material, tex_emit_node)
              
              tex_emit_node[1000] = emit_tex_node # Texture slot in Emission node
              material[OCT_MAT_EMISSION_LINK] = tex_emit_node

    except Exception as e:
        print(f"Error in SetupTextures: {e}")
        raise RuntimeError("Unable to setup texture")
