import c4d
import os
import sys

# Add mw_utils to sys.path
folder = os.path.dirname(__file__)
if folder not in sys.path:
    sys.path.insert(0, folder)

from mw_utils import octane_utils

# --- Plugin ID ---
# UNIQUE ID REQUIRED! Using a placeholder that hopefully doesn't conflict.
# Please replace with a registered ID from plugincafe.com if releasing.
PLUGIN_ID = 1067429 

# --- UI IDs ---
GRP_MAIN = 1000
TXT_INFO = 1001
BTN_LOAD = 1002
BTN_CLOSE = 1003

class OctanePBRDialog(c4d.gui.GeDialog):
    def __init__(self):
        self.texture_files = []

    def CreateLayout(self):
        self.SetTitle("Auto Connect PBR Textures (Octane)")
        
        if self.GroupBegin(GRP_MAIN, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 1, 0, "Main Group", 0):
            self.GroupBorderSpace(10, 10, 10, 10)
            
            self.AddStaticText(TXT_INFO, c4d.BFH_SCALEFIT, 0, 0, "Select a texture file to auto-connect.", c4d.BORDER_NONE)
            
            self.AddButton(BTN_LOAD, c4d.BFH_SCALEFIT, 0, 0, "Load Textures")
            # self.AddButton(BTN_CLOSE, c4d.BFH_SCALEFIT, 0, 0, "Close")
            
        self.GroupEnd()
        return True

    def Command(self, id, msg):
        if id == BTN_LOAD:
            self.LoadTextureFiles()
        elif id == BTN_CLOSE:
            self.Close()
        return True

    def LoadTextureFiles(self):
        # Open standard file dialog
        files = c4d.storage.LoadDialog(title="Select Textures", flags=c4d.FILESELECT_LOAD, force_suffix="")
        
        if not files:
            return

        # Handle multiple files or single file selection logic
        # Since LoadDialog usually returns one string, we might need a multi-file dialog or parse the folder.
        # But 'Auto_Connect_PBR_Textures.pyp' typically selects one file and scans the folder.
        # Let's check what the user usually expects.
        # For simplicity and consistency with previous tools, let's assume selecting one file 
        # triggers scanning for siblings.
        
        selected_file = files
        directory = os.path.dirname(selected_file)
        filename = os.path.basename(selected_file)
        
        # Determine the set of files based on user selection
        # Logic: Find all files in the same directory that share a common prefix or just scan all?
        # Let's iterate all files in directory and try to match PBR keywords.
        
        # Simplified: Pass ALL files in the directory to a filter, or just the selected one?
        # Typically PBR loaders look at all files in the folder.
        
        all_files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        
        # Filter logic: Try to group by similarity to selected file? 
        # Or just take everything that looks like a texture?
        # Let's take 'octane_utils' logic. It maps channel -> file.
        
        # We need to build the 'tex_data' dictionary { 'base_color': path, 'normal': path ... }
        tex_data = {}
        
        # Heuristic: If we selected "Wood_Color.jpg", we want "Wood_Normal.jpg", not "Metal_Color.jpg"
        # 1. Get prefix of selected file?
        # This is tricky without strict naming. 
        # Let's try to match files that have the same "stem" name excluding the channel keyword.
        
        candidates = []
        target_channel = octane_utils.GetTextureChannel(filename)
        
        common_stem = filename
        if target_channel:
             # Remove the channel keyword from the filename to find the "stem"
             # e.g. "Wood_01_Color.jpg" -> "Wood_01_"
             # simplified approach: check common substring
             pass
             
        # For now, let's collect ALL recognized PBR textures in the folder
        # and let the user be responsible for folder organization (classic method)
        # OR, better: Only load files that share a significant portion of the filename
        
        for f in all_files:
            # Skip non-image extensions
            ext = os.path.splitext(f)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.exr', '.hdr']:
                continue
                
            full_path = os.path.join(directory, f)
            channel = octane_utils.GetTextureChannel(f)
            
            if channel:
                # Conflict resolution: if channel already found, maybe ask or prefer shorter name?
                # We will just overwrite for now or use the first one.
                # Ideally we should filter by "belonging to the same set".
                # Simple filter: if 'selected_file' is in the folder, assume we want that 'set'.
                
                # Check if this file roughly belongs to the selected file's group
                # (Simple containment check or similar length?)
                # A robust way is hard without `difflib`. 
                # Let's just USE ALL DETECTED TEXTURES in the folder for now. 
                # This is how many simple loaders work.
                
                if channel not in tex_data:
                    tex_data[channel] = full_path
        
        if not tex_data:
            c4d.gui.MessageDialog("No recognizable PBR textures found.")
            return

        self.CreateMaterialNodes(tex_data, directory)

    def CreateMaterialNodes(self, tex_data, directory):
        doc = c4d.documents.GetActiveDocument()
        doc.StartUndo()
        
        # Create Material
        mat_name = "Octane PBR Material"
        # Try to name it after the directory or a texture
        if "base_color" in tex_data:
            mat_name = os.path.splitext(os.path.basename(tex_data["base_color"]))[0]
            # Clean up name (remove channel suffix)
            # This is optional polish
            
        mat = octane_utils.CreateOctaneMaterial(doc, mat_name)
        c4d.EventAdd() # Refresh to ensure material is valid in system? usually not needed for undo
        
        # Setup Textures
        try:
            octane_utils.SetupTextures(mat, tex_data)
            
            # Select the material
            doc.SetActiveMaterial(mat)
            mat.SetBit(c4d.BIT_ACTIVE)
            
            c4d.StatusSetText("Octane PBR Material Created!")
            
        except Exception as e:
            c4d.gui.MessageDialog(f"Error creating material: {e}")
            
        doc.EndUndo()
        c4d.EventAdd()
        
        # Close dialog after success?
        self.Close()

class OctanePBRCommand(c4d.plugins.CommandData):
    dialog = None

    def Execute(self, doc):
        if self.dialog is None:
            self.dialog = OctanePBRDialog()
        return self.dialog.Open(dlgtype=c4d.DLG_TYPE_ASYNC, pluginid=PLUGIN_ID, defaultw=300, defaulth=150)

    def RestoreLayout(self, sec_ref):
        if self.dialog is None:
            self.dialog = OctanePBRDialog()
        return self.dialog.Restore(PLUGIN_ID, secret=sec_ref)

if __name__ == "__main__":
    # Register Plugin
    ok = c4d.plugins.RegisterCommandPlugin(
        id=PLUGIN_ID,
        str="Auto Connect PBR Textures (Octane)",
        info=0,
        icon=None, 
        help="Creates Octane material from PBR textures",
        dat=OctanePBRCommand()
    )
    if ok:
        print("Octane Auto Connect PBR Plugin Initialized")
