import c4d
import os
import sys
import json

# Add mw_utils path
folder = os.path.dirname(__file__)
if folder not in sys.path:
    sys.path.insert(0, folder)

from mw_utils import octane_utils as oc_utils

# --- Plugin ID ---
PLUGIN_ID = 1067430 # Temporary ID

# --- UI IDs ---
GRP_MAIN = 1000
CHK_TRIPLANAR = 1008
CHK_PER_TEXTURE = 1009
BTN_APPLY = 1012
BTN_CLOSE = 1013

class TextureTransformDialog(c4d.gui.GeDialog):
    def __init__(self):
        self.params = {
            "triplanar": False,
            "per_texture": False
        }
        self.settings_file = os.path.join(folder, "mw_utils", "settings_transform.json")

    def load_settings(self):
        if not os.path.exists(self.settings_file):
            return

        try:
            with open(self.settings_file, 'r') as f:
                all_settings = json.load(f)
            if "OctaneTextureTransform" in all_settings:
                saved_params = all_settings["OctaneTextureTransform"]
                for key, value in saved_params.items():
                    if key in self.params:
                        self.params[key] = value
        except Exception as e:
            print(f"Error loading settings: {e}")

    def save_settings(self):
        try:
            all_settings = {}
            if os.path.exists(self.settings_file):
                 try:
                    with open(self.settings_file, 'r') as f:
                        all_settings = json.load(f)
                 except:
                     pass

            all_settings["OctaneTextureTransform"] = self.params
            with open(self.settings_file, 'w') as f:
                json.dump(all_settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def CreateLayout(self):
        self.SetTitle("Quick Texture Transform (Octane)")

        self.GroupBegin(GRP_MAIN, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 1, 0, "Controls", 0)
        self.GroupBorderSpace(10, 5, 10, 5)

        self.AddCheckbox(CHK_TRIPLANAR, c4d.BFH_LEFT, 0, 0, "Use Triplanar Projection")
        self.AddCheckbox(CHK_PER_TEXTURE, c4d.BFH_LEFT, 0, 0, "Create Node per Texture")
        
        self.AddSeparatorH(c4d.BFH_SCALEFIT)
        
        if self.GroupBegin(0, c4d.BFH_CENTER, 2, 0, "", 0):
            self.GroupBorderSpace(0, 10, 0, 0)
            self.AddButton(BTN_APPLY, c4d.BFH_SCALEFIT, 100, 0, "Apply")
            self.AddButton(BTN_CLOSE, c4d.BFH_SCALEFIT, 100, 0, "Close")
        self.GroupEnd()
    
        self.GroupEnd()
        return True

    def InitValues(self):
        self.load_settings()
        self.SetBool(CHK_TRIPLANAR, self.params["triplanar"])
        self.SetBool(CHK_PER_TEXTURE, self.params["per_texture"])
        return True

    def Command(self, id, msg):
        if id == BTN_CLOSE:
            self.Close()
            return True
            
        elif id == BTN_APPLY:
            self.params["triplanar"] = self.GetBool(CHK_TRIPLANAR)
            self.params["per_texture"] = self.GetBool(CHK_PER_TEXTURE)
            self.save_settings()
            
            doc = c4d.documents.GetActiveDocument()
            self.ApplyControls(doc)
            return True
            
        return True

    def ApplyControls(self, doc):
        # 1. Get Active Material
        mat = doc.GetActiveMaterial()
        if not mat:
            c4d.gui.MessageDialog("Please select an Octane Material.")
            return

        # 2. Find ALL Image Texture Nodes (Selection is not supported in Octane Node Editor)
        # We iterate through all shaders to find Image Textures
        selected_textures = []
        
        def scan_shader(shader):
            while shader:
                if shader.CheckType(oc_utils.ID_OCT_IMAGE_TEXTURE):
                    # We accept ALL image textures because we cannot check for selection
                    selected_textures.append(shader)
                
                if shader.GetDown():
                    scan_shader(shader.GetDown())
                shader = shader.GetNext()

        scan_shader(mat.GetFirstShader())
        
        if not selected_textures:
            c4d.gui.MessageDialog("No Image Texture nodes found in the material.")
            return

        doc.StartUndo()
        
        # 3. Create Nodes
        # Logic:
        # If per_texture: Create Transform/Triplanar for EACH texture
        # Else: Create ONE Transform/Triplanar and connect to ALL
        
        common_transform = None
        common_triplanar = None
        
        if not self.params["per_texture"]:
            # Create Common Nodes
            common_transform = c4d.BaseList2D(oc_utils.ID_OCT_TRANSFORM)
            oc_utils.AddShaderToMaterial(mat, common_transform)
            common_transform.SetName("UV Transform")
            
            if self.params["triplanar"]:
                common_triplanar = c4d.BaseList2D(oc_utils.ID_OCT_TRIPLANAR_PROJECTION)
                oc_utils.AddShaderToMaterial(mat, common_triplanar)
                common_triplanar.SetName("Triplanar Projection")

        for tex in selected_textures:
            transform_node = common_transform
            triplanar_node = common_triplanar
            
            if self.params["per_texture"]:
                transform_node = c4d.BaseList2D(oc_utils.ID_OCT_TRANSFORM)
                oc_utils.AddShaderToMaterial(mat, transform_node)
                transform_node.SetName(f"{tex.GetName()} Transform")
                
                if self.params["triplanar"]:
                    triplanar_node = c4d.BaseList2D(oc_utils.ID_OCT_TRIPLANAR_PROJECTION)
                    oc_utils.AddShaderToMaterial(mat, triplanar_node)
                    triplanar_node.SetName(f"{tex.GetName()} Projection")

            # Connect Transform
            # Connect to Transform Link (1002)
            tex[oc_utils.IMAGETEXTURE_TRANSFORM_LINK] = transform_node
            
            # Connect Triplanar (if enabled)
            if self.params["triplanar"] and triplanar_node:
                # Connect to Projection Link (1003)
                tex[oc_utils.IMAGETEXTURE_PROJECTION_LINK] = triplanar_node
            
            tex.Message(c4d.MSG_UPDATE)

        doc.EndUndo()
        c4d.EventAdd()
        c4d.StatusSetText(f"Connected {len(selected_textures)} textures.")

class QuickTextureTransformCommand(c4d.plugins.CommandData):
    dialog = None

    def Execute(self, doc):
        if self.dialog is None:
            self.dialog = TextureTransformDialog()
        return self.dialog.Open(c4d.DLG_TYPE_ASYNC, pluginid=PLUGIN_ID, defaultw=250, defaulth=150)

    def RestoreLayout(self, sec_ref):
        if self.dialog is None:
            self.dialog = TextureTransformDialog()
        return self.dialog.Restore(pluginid=PLUGIN_ID, secret=sec_ref)

if __name__ == "__main__":
    # Icon (optional)
    bmp = None 
    # Can use generic icon or reuse from original
    
    c4d.plugins.RegisterCommandPlugin(
        id=PLUGIN_ID,
        str="Quick Texture Transform (Octane)",
        info=0,
        icon=bmp,
        help="Creates Octane Transform controls",
        dat=QuickTextureTransformCommand()
    )
    print("Octane Quick Texture Transform Initialized")
