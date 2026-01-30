import c4d
import maxon
import os
import sys
import shutil
import re

# Add utils path
current_dir = os.path.dirname(__file__)
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Import Octane Utils
from mw_utils import octane_utils

# Add dependencies path (Same as original)
if sys.platform == 'win32':
    dep_dir = os.path.join(current_dir, "dependencies", "win64")
elif sys.platform == 'darwin':
    dep_dir = os.path.join(current_dir, "dependencies", "osx")
else:
    dep_dir = os.path.join(current_dir, "dependencies")

if os.path.exists(dep_dir) and dep_dir not in sys.path:
    sys.path.append(dep_dir)

# Try to import PIL
PIL_ERROR_MSG = None
try:
    from PIL import Image
except ImportError as e:
    Image = None
    PIL_ERROR_MSG = str(e)
    # print(f"Failed to import PIL: {e}")

# --- Plugin ID ---
PLUGIN_ID = 1067431 # Temporary ID for Octane Resize

ID_TREEVIEW = 1000
ID_BTN_ORIGINAL = 1001
ID_BTN_RESIZE = 1002
ID_MENU_OPEN_TEX = 2001
ID_MENU_DELETE_UNUSED = 2002

def ResolveTexturePath(doc, path_str):
    """Resolves a texture path to an absolute path. (Same as original)"""
    if not path_str or not doc:
        return None
    
    if os.path.isabs(path_str):
        return path_str if os.path.exists(path_str) else None

    doc_path = doc.GetDocumentPath()
    if not doc_path:
        return None
        
    cand1 = os.path.join(doc_path, path_str)
    if os.path.exists(cand1):
        return cand1
        
    cand2 = os.path.join(doc_path, "tex", path_str)
    if os.path.exists(cand2):
        return cand2
        
    return None

def GetRootTextureName(filename):
    """Strips sequence of '_Low' suffixes to find the root name."""
    name, ext = os.path.splitext(filename)
    while name.endswith("_Low"):
        name = name[:-4]
    return name, ext

class TextureObject(object):
    """Stores data for a single row in the TreeView."""
    def __init__(self, node, path, filename, resolution_str, size_str, is_selected=False):
        self.node = node # This is now a c4d.BaseShader (Octane)
        self.path = path
        self.filename = filename
        self.resolution_str = resolution_str
        self.size_str = size_str
        self.selected = is_selected

    @property
    def IsSelected(self):
        return self.selected

    def Select(self):
        self.selected = True

    def Deselect(self):
        self.selected = False

    def __repr__(self):
        return f"TextureObject({self.filename})"
    
    def __str__(self):
        return self.filename

class TextureTreeViewFunctions(c4d.gui.TreeViewFunctions):
    """Handles rendering and interaction for the TreeView."""

    def __init__(self, texture_list):
        self.texture_list = texture_list
        # Color settings
        self.color_item_normal = c4d.COLOR_TEXT
        self.color_item_selected = c4d.COLOR_TEXT_SELECTED
        self.color_background_normal = c4d.COLOR_BG_DARK2
        self.color_background_alternate = c4d.COLOR_BG_DARK1
        self.color_background_selected = c4d.COLOR_BG_HIGHLIGHT
        
        self.col_padding = 10
        self.text_offset_x = 5

    def SetTextureList(self, texture_list):
        self.texture_list = texture_list

    def GetFirst(self, root, userdata):
        if not self.texture_list:
            return None
        return self.texture_list[0]

    def GetDown(self, root, userdata, obj):
        return None

    def GetNext(self, root, userdata, obj):
        try:
            idx = self.texture_list.index(obj)
            if idx < len(self.texture_list) - 1:
                return self.texture_list[idx + 1]
        except ValueError:
            return None
        return None

    def GetPred(self, root, userdata, obj):
        try:
            idx = self.texture_list.index(obj)
            if idx > 0:
                return self.texture_list[idx - 1]
        except ValueError:
            return None
        return None

    def IsSelected(self, root, userdata, obj):
        return obj.IsSelected

    def Select(self, root, userdata, obj, mode):
        # Update internal state and OCTANE Shader Selection
        
        # Deselect all first if NEW selection
        doc = c4d.documents.GetActiveDocument()
        
        if mode == c4d.SELECTION_NEW:
             for item in self.texture_list:
                 item.Deselect()
                 if item.node:
                     item.node.DelBit(c4d.BIT_ACTIVE)
             
             if obj:
                 obj.Select()
                 if obj.node:
                     obj.node.SetBit(c4d.BIT_ACTIVE)
                     
        elif mode == c4d.SELECTION_ADD:
            if obj:
                obj.Select()
                if obj.node:
                    obj.node.SetBit(c4d.BIT_ACTIVE)
                    
        elif mode == c4d.SELECTION_SUB:
            if obj:
                obj.Deselect()
                if obj.node:
                    obj.node.DelBit(c4d.BIT_ACTIVE)
        
        c4d.EventAdd()

    def GetId(self, root, userdata, obj):
        return hash(obj)

    def GetColumnWidth(self, root, userdata, obj, col, area):
        if col == 1: # Filename
            if obj:
                 return area.DrawGetTextWidth(obj.filename) + self.col_padding
            return 100
        elif col == 2: # Resolution
            if obj:
                 return area.DrawGetTextWidth(obj.resolution_str) + self.col_padding
            return 50
        elif col == 3: # File Size
            if obj:
                 return area.DrawGetTextWidth(obj.size_str) + self.col_padding
            return 50
        return 50

    def GetHeaderColumnWidth(self, root, userdata, col, area):
         return self.GetColumnWidth(root, userdata, None, col, area)

    def DrawCell(self, root, userdata, obj, col, drawinfo, bgColor):
        if not obj: return
        
        canvas = drawinfo["frame"]
        xpos = drawinfo["xpos"]
        ypos = drawinfo["ypos"]
        
        text = ""
        if col == 1:
            text = obj.filename
        elif col == 2:
            text = obj.resolution_str
        elif col == 3:
            text = obj.size_str
            
        if obj.IsSelected:
            txtColorDict = canvas.GetColorRGB(self.color_item_selected)
        else:
            txtColorDict = canvas.GetColorRGB(self.color_item_normal)
            
        txtColorVector = c4d.Vector(
            txtColorDict["r"] / 255.0,
            txtColorDict["g"] / 255.0,
            txtColorDict["b"] / 255.0
        )
        
        canvas.DrawSetTextCol(txtColorVector, bgColor)
        canvas.DrawText(text, xpos + self.text_offset_x, ypos + 2)

    def GetLineHeight(self, root, userdata, obj, col, area):
        return 18 

    def IsResizeColAllowed(self, root, userdata, lColID):
        return True

    def IsTristate(self, root, userdata):
        return False

    def IsOpened(self, root, userdata, obj):
        return False

    def GetBackgroundColor(self, root, userdata, obj, line, col):
        if not obj: return None
        if obj.IsSelected:
            return self.color_background_selected
        return None

# --- Helper to collect Octane Shaders ---
def GetOctaneTextures(material):
    """
    Recursively finds all Image Texture shaders in the material.
    """
    textures = []
    if not material:
        return textures
        
    # Recursive scanner
    def scan_shader(shader):
        while shader:
            if shader.CheckType(octane_utils.ID_OCT_IMAGE_TEXTURE):
                textures.append(shader)
            
            # Check children (Down)
            if shader.GetDown():
                scan_shader(shader.GetDown())
            
            # Check siblings (Next)
            shader = shader.GetNext()

    # Start with the first shader of the material
    scan_shader(material.GetFirstShader())
    return textures

class ResizeTextureDialog(c4d.gui.GeDialog):
    """Main Dialog for the plugin."""

    def __init__(self):
        self.treegui = None
        self.texture_list = []
        self.tree_funcs = TextureTreeViewFunctions([]) 

    def CreateLayout(self):
        self.SetTitle("Resize Texture Resolution (Octane)")
        
        self.MenuFlushAll()
        self.MenuSubBegin("Options")
        self.MenuAddString(ID_MENU_OPEN_TEX, "Open tex Folder...")
        self.MenuAddString(ID_MENU_DELETE_UNUSED, "Delete Unused Textures(Selected Only)")
        self.MenuSubEnd()
        self.MenuFinished()

        settings = c4d.BaseContainer()
        settings.SetBool(c4d.TREEVIEW_BORDER, True)
        settings.SetBool(c4d.TREEVIEW_HAS_HEADER, True)
        settings.SetBool(c4d.TREEVIEW_HIDE_LINES, False)
        settings.SetBool(c4d.TREEVIEW_MOVE_COLUMN, True)
        settings.SetBool(c4d.TREEVIEW_RESIZE_HEADER, True)
        settings.SetBool(c4d.TREEVIEW_FIXED_LAYOUT, True)
        settings.SetBool(c4d.TREEVIEW_ALTERNATE_BG, True)
        settings.SetBool(c4d.TREEVIEW_NOENTERRENAME, True)
        settings.SetBool(c4d.TREEVIEW_NO_DELETE, True)
        settings.SetBool(c4d.TREEVIEW_NO_BACK_DELETE, True)

        self.treegui = self.AddCustomGui(ID_TREEVIEW, c4d.CUSTOMGUI_TREEVIEW, "", c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 0, 0, settings)

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 2, 0, "", 0)
        self.GroupBorderSpace(5, 5, 5, 5) 
        self.AddButton(ID_BTN_ORIGINAL, c4d.BFH_SCALEFIT, 0, 0, "Original")
        self.AddButton(ID_BTN_RESIZE, c4d.BFH_SCALEFIT, 0, 0, "Resize to 50%")
        self.GroupEnd()

        if self.treegui:
            self.treegui.SetRoot(self.treegui, self.tree_funcs, None)

        return True

    def InitValues(self):
        layout = c4d.BaseContainer()
        COL_FILENAME = 1
        COL_RESOLUTION = 2
        COL_SIZE = 3
        
        layout.SetLong(COL_FILENAME, c4d.LV_USER)
        layout.SetLong(COL_RESOLUTION, c4d.LV_USER)
        layout.SetLong(COL_SIZE, c4d.LV_USER)
        
        self.treegui.SetLayout(3, layout)
        
        self.treegui.SetHeaderText(COL_FILENAME, "Filename")
        self.treegui.SetHeaderText(COL_RESOLUTION, "Resolution")
        self.treegui.SetHeaderText(COL_SIZE, "File Size")
        
        self.RefreshTextureList()
        return True

    def CoreMessage(self, id, msg):
        if id == c4d.EVMSG_CHANGE:
            self.RefreshTextureList()
        return c4d.gui.GeDialog.CoreMessage(self, id, msg)

    def RefreshTextureList(self):
        doc = c4d.documents.GetActiveDocument()
        if not doc: return

        # Get Materials
        mat = doc.GetActiveMaterial()
        if not mat: return
        
        # Check if it's Octane
        # Note: We assume it's Octane if we find Octane Shaders, or we can check ID via octane_utils.
        # But for robustness, just scanning shaders is fine.
        
        nodes_found = GetOctaneTextures(mat)
        
        # Build Texture Objects
        new_list = []
        for node in nodes_found:
             # Check if selected? (Using bits)
             is_active = node.GetBit(c4d.BIT_ACTIVE)
             
             # Get Path from Shader
             current_path = node[octane_utils.IMAGETEXTURE_FILE]
             if not current_path:
                 current_path = ""
             else:
                 current_path = str(current_path)

             abs_path = ResolveTexturePath(doc, current_path)
             filename = os.path.basename(current_path) if current_path else "No Path"
             res_str = "Unknown"
             size_str = "Unknown"

             if abs_path:
                 try:
                     size_bytes = os.path.getsize(abs_path)
                     size_mb = size_bytes / (1024 * 1024)
                     size_str = f"{size_mb:.2f} MB"
                 except:
                     size_str = "Error"
                 
                 res_found = False
                 if Image:
                     try:
                         with Image.open(abs_path) as img:
                             res_str = f"{img.width}x{img.height}"
                             res_found = True
                     except:
                         pass
                 
                 if not res_found:
                     if not Image:
                          res_str = "PIL Missing"
                     else:
                          res_str = "Load Failed"
             
             new_list.append(TextureObject(node, current_path, filename, res_str, size_str, is_active))

        self.texture_list = new_list
        self.tree_funcs.SetTextureList(self.texture_list)
        self.treegui.Refresh()

    def Command(self, id, msg):
        if id == ID_BTN_RESIZE:
            self.ResizeTo50percent()
        elif id == ID_BTN_ORIGINAL:
            self.Original()
        elif id == ID_MENU_OPEN_TEX:
            self.OpenTexFolder()
        elif id == ID_MENU_DELETE_UNUSED:
            self.DeleteUnusedResizedTextures()
        return True

    def ResizeTo50percent(self):
        doc = c4d.documents.GetActiveDocument()
        doc_path = doc.GetDocumentPath()
        if not doc_path:
             c4d.gui.MessageDialog("Please save project first.")
             return
             
        tex_folder = os.path.join(doc_path, "tex")
        if not os.path.exists(tex_folder):
            try: os.makedirs(tex_folder)
            except: pass

        selected_objs = [obj for obj in self.texture_list if obj.selected]
        if not selected_objs: selected_objs = self.texture_list 

        if not selected_objs:
             c4d.gui.MessageDialog("No textures to resize.")
             return

        processed = 0
        
        for obj in selected_objs:
             abs_path = ResolveTexturePath(doc, obj.path)
             if not abs_path: continue

             filename = os.path.basename(abs_path)
             name, ext = os.path.splitext(filename)
             
             new_filename = f"{name}_Low{ext}"
             target_path = os.path.join(tex_folder, new_filename)
             
             original_in_tex = os.path.join(tex_folder, filename)
             if os.path.abspath(abs_path) != os.path.abspath(original_in_tex):
                 if not os.path.exists(original_in_tex):
                     try: shutil.copy2(abs_path, original_in_tex)
                     except: pass

             try:
                 if not os.path.exists(target_path):
                     resize_and_strip_metadata(abs_path, target_path)
                 
                 # Set Port (Octane)
                 obj.node[octane_utils.IMAGETEXTURE_FILE] = target_path
                 obj.node.Message(c4d.MSG_UPDATE)
                 
                 processed += 1
             except Exception as e:
                 print(f"Failed to resize {filename}: {e}")

        if processed > 0:
            c4d.EventAdd()
            self.RefreshTextureList()

    def Original(self):
        doc = c4d.documents.GetActiveDocument()
        
        selected_objs = [obj for obj in self.texture_list if obj.selected]
        if not selected_objs: selected_objs = self.texture_list
             
        processed = 0
        
        for obj in selected_objs:
            current_path = obj.path
            filename = os.path.basename(current_path)
            
            base_name, ext = GetRootTextureName(filename)
            original_name = base_name + ext
                
            dir_path = os.path.dirname(current_path)
            new_path_str = os.path.join(dir_path, original_name)
            
            # Set Port (Octane)
            obj.node[octane_utils.IMAGETEXTURE_FILE] = new_path_str
            obj.node.Message(c4d.MSG_UPDATE)
            processed += 1

        if processed > 0:
            c4d.EventAdd()
            self.RefreshTextureList()

    def OpenTexFolder(self):
        # ... (Same as original code)
        doc = c4d.documents.GetActiveDocument()
        if not doc: return
        doc_path = doc.GetDocumentPath()
        if not doc_path: return
        tex_folder = os.path.join(doc_path, "tex")
        if not os.path.exists(tex_folder): tex_folder = doc_path
        c4d.storage.ShowInFinder(tex_folder)

    def DeleteUnusedResizedTextures(self):
        # ... (Same logic as original, just re-implementing briefly for completeness)
        import re
        doc = c4d.documents.GetActiveDocument()
        doc_path = doc.GetDocumentPath()
        if not doc_path: return
        tex_folder = os.path.join(doc_path, "tex")
        
        selected_objs = [obj for obj in self.texture_list if obj.selected]
        if not selected_objs: return

        if not c4d.gui.QuestionDialog("Delete unused resized textures for selected?"): return

        deleted_files = []
        for obj in selected_objs:
            current_path = obj.path
            if not current_path: continue
            abs_path = ResolveTexturePath(doc, current_path)
            if not abs_path: continue
            
            filename = os.path.basename(abs_path)
            base_name, ext = GetRootTextureName(filename)
            
            try: files = os.listdir(tex_folder)
            except: continue
            
            pattern = re.compile(f"^{re.escape(base_name)}(_Low)+{re.escape(ext)}$", re.IGNORECASE)
            
            for f in files:
                if pattern.match(f):
                    full_path = os.path.join(tex_folder, f)
                    if os.path.abspath(full_path).lower() != os.path.abspath(abs_path).lower():
                        try:
                            os.remove(full_path)
                            deleted_files.append(f)
                        except: pass
        
        if deleted_files:
            c4d.gui.MessageDialog(f"Deleted {len(deleted_files)} files.")
        else:
            c4d.gui.MessageDialog("No unused files found.")

def resize_and_strip_metadata(input_path, output_path):
    # Same as original implementation
    ext = os.path.splitext(input_path)[1].lower()
    if ext in ['.exr', '.hdr']:
        raise Exception(f"Unsupported format: {ext}")

    if not Image:
        raise ImportError("PIL not loaded")
    
    with Image.open(input_path) as img:
        # Calculate new size (50%)
        new_size = (max(1, img.width // 2), max(1, img.height // 2))
        resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # Clean metadata
        clean_img = Image.new(resized_img.mode, resized_img.size)
        clean_img.putdata(list(resized_img.getdata()))
        
        ext = os.path.splitext(output_path)[1].lower()
        if ext in ['.jpg', '.jpeg']:
            clean_img.save(output_path, "JPEG", optimize=True, quality=85)
        elif ext in ['.png']:
             clean_img.save(output_path, "PNG", optimize=True)
        elif ext in ['.tif', '.tiff']:
             clean_img.save(output_path, "TIFF")
        else:
             clean_img.save(output_path)

class ResizeTextureCommand(c4d.plugins.CommandData):
    dialog = None

    def Execute(self, doc):
        if self.dialog is None:
            self.dialog = ResizeTextureDialog()
        return self.dialog.Open(dlgtype=c4d.DLG_TYPE_ASYNC, pluginid=PLUGIN_ID, defaultw=500, defaulth=300)

    def RestoreLayout(self, sec_ref):
        if self.dialog is None:
            self.dialog = ResizeTextureDialog()
        return self.dialog.Restore(PLUGIN_ID, sec_ref)

if __name__ == "__main__":
    icon_path = os.path.join(os.path.dirname(__file__), "Resize_Texture_Resolution.tif")
    bmp = c4d.bitmaps.BaseBitmap()
    if os.path.exists(icon_path):
        bmp.InitWith(icon_path)
    else:
        bmp = None
        
    c4d.plugins.RegisterCommandPlugin(
        id=PLUGIN_ID,
        str="Resize Texture Resolution (Octane)",
        info=0,
        icon=bmp, 
        help="Manage texture resolutions for Octane",
        dat=ResizeTextureCommand()
    )
    print("Octane Resize Plugin Initialized")
