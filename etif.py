from exiftool import ExifToolHelper
from PIL import Image, ImageDraw, ImageFont, ImageOps
from PyQt5.QtWidgets import QProgressBar, QApplication
from skimage.io import imread
from skimage.transform import resize
import rawpy
import os
import json
# from app_py import AppSettings

# LIB: rawpy
# with ExifToolHelper() as et:
#     #"J:/2024_03/20240324/RAW/IMG_2294.CR2"
#     for d in et.get_metadata("J:/DSCF0082.RAF"):
#         for k, v in d.items():
#             print(f"Dict: {k} = {v}")

# with ExifToolHelper() as et:
#     #"J:/2024_03/20240324/RAW/IMG_2294.CR2"
#     for d in et.get_metadata("J:/2024_03/20240316/RAW/IMG_0840.CR2"):
#         for k, v in d.items():
#             print(f"Dict: {k} = {v}")
# with ExifToolHelper() as et:
#     for d in et.get_metadata("J:/2024_03/20240331/DSCF0080.RAF"):
#         for k, v in d.items():
#             print(f"Dict: {k} = {v}")

DEBUG_MODE = False
def debug(error_code, func_name, message):
    if not DEBUG_MODE:
        return
    print(f"{error_code:>6} | {func_name:>25} | {message}")

class AppSettings():
    def __init__(self, settings_path: str):
        self.settings_path = settings_path
        self.settings = self.readSettings()

    def readSettings(self):
        # Opening JSON file
        f = open(self.settings_path)

        # returns JSON object as a dictionary
        data = json.load(f)
        return data
    
    def getSettings(self):
        return self.settings
    
    def getOutputPath(self):
        return self.settings["settings"]["Output_Path"] + "/"
    
    def getGeneratorSettings(self):
        return {
            "Default_Font": self.settings["settings"]["Font"].get("Default_Font", None),
            "Font_40": self.settings["settings"]["Font"].get("Font_40", None),
            "Font_60": self.settings["settings"]["Font"].get("Font_60", None),
            "Title_Font_80": self.settings["settings"]["Font"].get("Title_Font_80", None),
            "Model_Font_80": self.settings["settings"]["Font"].get("Model_Font_80", None),
        }

class MetadataGenerator:
    def __init__(self, brand_logo_path, settings: AppSettings) -> None:
        self.brand_logo_path = brand_logo_path
        self.settings = settings
        self.settings_dict = settings.getGeneratorSettings()
        self.FOOTER_HEIGHT = 200
        self.PADDING_WIDTH = 60
        self.connected_progress_bar = False
        self.show_images = True
        self.progress_callback = None

    def readRawMetadata(self, files: list) -> dict:
        exif = {}
        with ExifToolHelper() as et:
            for d in et.get_tags(
                files,
                tags=[
                    "Make",
                    "Model",
                    "ExifImageWidth",
                    "ExifImageHeight",
                    "RawImageFullWidth",
                    "RawImageFullHeight",
                    "ImageWidth",
                    "ImageHeight",
                    "ImageCount",
                    "Iso",
                    "FNumber",
                    "ExposureTime",
                    "FocalLength",
                    "Orientation"
                ],
            ):
                file = d.get("SourceFile")
                exif[file] = {}
                for k, v in d.items():
                    key = k.split(":")[-1]
                    if key == "ExposureTime":
                        v = round(1 / float(v))
                        v = f"1/{v}"
                    # print(f"Dict: {key} = {v}")
                    exif[file][key] = v

        metadata = {}
        for filename, data in exif.items():
            if data.get("Make", None) is None:
                continue
            else:
                debug("DEBUG", MetadataGenerator.readRawMetadata.__name__, ("RAW EXIF DATA:",data))
                if (data.get("RawImageFullWidth", 0) * data.get("RawImageFullHeight", 0) > data.get("ExifImageWidth", 0) *  data.get("ExifImageHeight", 0)):
                    width = data.get("RawImageFullWidth")
                    height = data.get("RawImageFullHeight")
                else:
                    width = data.get("ExifImageWidth") if data.get("ExifImageWidth", 0) > 0 else data.get("ImageWidth")
                    height = data.get("ExifImageHeight") if data.get("ExifImageHeight", 0) > 0 else data.get("ImageHeight")
                if data.get("Orientation") in [5,6,7,8]:
                    width, height = height, width
                metadata[filename] = {
                    "BRAND": data.get("Make", None),
                    "MODEL": data.get("Model", None),
                    "WIDTH": width,
                    "HEIGHT": height,
                    "IMAGECOUNT": data.get("ImageCount"),
                    "ISO": data.get("ISO"),
                    "FNUMBER": round(data.get("FNumber"), 1),
                    "EXPOSURE": data.get("ExposureTime"),
                    "FOCALLENGTH": round(data.get("FocalLength")),
                    "ORIENTATION": data.get("Orientation"),
                }
        debug("DEBUG", MetadataGenerator.readRawMetadata.__name__, ("TRIMMED EXIF DATA:",metadata))
        return metadata

    # Create a black placeholder image that will be added to the camera settings summary image as indicator of original image postion
    def createPlaceholder(self, width: int, height: int) -> Image:
        new_image = Image.new("RGBA", (width, height), color="black")
        return new_image

    # Main function to create camera settings summary images
    def createCoverWithMetadata(
        self, width, height, metadata, image_placeholder, output_file=None
    ):
        # Create a new blank TIFF image with the given width and height
        # print(width, height)
        # print(metadata)
        new_image = Image.new("RGBA", (width, height), color="white")
        draw = ImageDraw.Draw(new_image)
        font_40 = ImageFont.truetype(self.settings_dict.get("Font_40", self.settings_dict["Default_Font"]), size=40)
        font_60 = ImageFont.truetype(self.settings_dict.get("Font_60", self.settings_dict["Default_Font"]), size=60)
        title_font_80 = ImageFont.truetype(self.settings_dict.get("Title_Font_80", self.settings_dict["Default_Font"]), size=80)
        model_font_80 = ImageFont.truetype(self.settings_dict.get("Model_Font_80", self.settings_dict["Default_Font"]), size=80)
        # Draw metadata text onto the image
        footer_x = self.PADDING_WIDTH
        footer_y = height - self.FOOTER_HEIGHT
        x = self.PADDING_WIDTH
        y = height - self.FOOTER_HEIGHT + 10
        brand = metadata.get("BRAND", None)

        # Model name section
        model = self.trimModelBrand(brand, metadata.get("MODEL", None))
        draw.text((footer_x, footer_y + 50), model, fill="black", font=model_font_80)

        
        # Calculate camera details font size
        camera_details = f"{metadata.get('FOCALLENGTH')}mm  ISO-{metadata.get('ISO')}  f/{metadata.get('FNUMBER')}  {metadata.get('EXPOSURE')}"
        text_left, text_top, text_right, text_bottom = draw.textbbox(
            (x, y), camera_details, font=title_font_80
        )
        text_width, text_height = (text_right - text_left, text_bottom - text_top)
        debug("DEBUG", MetadataGenerator.createCoverWithMetadata.__name__, ("Text Size: ",text_width,text_height))

        if brand:
            # Brand logo section
            brand_path = f"{self.brand_logo_path}/{brand}.png"
            logo_image = Image.open(brand_path).convert("RGBA")
            logo_image = ImageOps.contain(logo_image, (width, self.FOOTER_HEIGHT))
            logo_size = logo_image.size
            debug("DEBUG", MetadataGenerator.createCoverWithMetadata.__name__, ("Brand Logo Size: ", logo_image.size))
            brand_position, details_position = self.calculateBrandPosition(
                width, text_width, logo_size[0]
            )
            debug("DEBUG", MetadataGenerator.createCoverWithMetadata.__name__, ("Brand Position: ", brand_position, "Model Position: ", details_position))
            new_image.paste(logo_image, (brand_position, footer_y), mask=logo_image)

        # Camera details section
        draw.text(
            (details_position, footer_y + 50), camera_details, fill="black", font=title_font_80
        )

        # Seperator line for brand logo and camera details
        shape = [
            (details_position - 28, footer_y + 30),
            (details_position - 28, height - 30),
        ]
        draw.line(shape, fill="#D3D3D3", width=10)

        # Image placeholder for the camera details cover
        new_image.paste(image_placeholder, (self.PADDING_WIDTH, self.PADDING_WIDTH))

        # Save the image as a PNG file
        new_image.save(self.settings.getOutputPath() + output_file + ".png", format="png")
        if self.show_images:
            new_image.show()

    # Trimmed out brand name from model name to avoid redundancy
    def trimModelBrand(self, brand: str, model: str) -> str:
        trimmed_text = model.replace(brand + " ", "")
        return trimmed_text

    # Calculate the brand logo position, and model name position based on image width
    def calculateBrandPosition(
        self, image_width, model_width, logo_width
    ) -> tuple[int, int]:
        RIGHT_PADDING = self.PADDING_WIDTH
        LOGO_TEXT_GAP = 60
        logo_position = (
            image_width - RIGHT_PADDING - model_width - LOGO_TEXT_GAP - logo_width
        )
        model_position = image_width - RIGHT_PADDING - model_width
        # print(image_width , RIGHT_PADDING , model_width , LOGO_TEXT_GAP , logo_width)
        return round(logo_position), round(model_position)

    def readImage(self, file_path: str, size: tuple, settings: dict = {}):
        try:
            width, height = size
            raw_image = imread(file_path)
            resized_image = resize(raw_image, (height, width), preserve_range=True, anti_aliasing=True)
            pil_image = Image.fromarray(resized_image.astype('uint8'))
        except OSError as err:
            debug("ERROR",MetadataGenerator.readImage.__name__, "USING ALTERNATIVE RAWPY TO READ IMAGE")
            # Load the RAW file
            with rawpy.imread(file_path) as raw:
                # Convert the RAW data to an RGB image
                rgb = raw.postprocess(
                    use_camera_wb=True,
                    demosaic_algorithm=rawpy.DemosaicAlgorithm.AAHD,
                    output_color=rawpy.ColorSpace.sRGB,
                    median_filter_passes=2,
                    no_auto_bright=True, 
                )        
            # Create a PIL Image object from the RGB data
            pil_image = Image.fromarray(rgb.astype("uint8"))
            pil_image = pil_image.resize((width, height))

        if settings.get("MIRROR", False):
            # print("MIRRORED")
            pil_image = ImageOps.mirror(pil_image)
        # print(settings.get("ROTATION", 0))
        rotation = min(int(settings.get("ROTATION", 0)),360)
        pil_image = pil_image.rotate(rotation, resample=Image.NEAREST, expand=True)
        # print(pil_image.size)
        # if abs(rotation) in [90, 270]:
        #     pil_image = pil_image.transpose(Image.TRANSPOSE)
        # print(pil_image.size)


        # pil_image.show()
        return pil_image

    # Generate camera settings summary image based on metadata given
    def generateCover(self, metadata: dict, combine_original_images: bool = False) -> None:
        progress = int(89 / len(metadata))
        for file, data in metadata.items():
            filename = ".".join(file.split("/")[-1].split(".")[:-1])
            width = data.get("WIDTH")
            height = data.get("HEIGHT")

            if data.get("ROTATION") in ["90", "270"]:
                width, height = height, width

            image_width = width + self.PADDING_WIDTH * 2
            image_height = height + self.PADDING_WIDTH + self.FOOTER_HEIGHT
            
            
            image_placeholder = None
            if not combine_original_images:
                image_placeholder = self.createPlaceholder(
                    width, height
                )
            else:
                image_placeholder = self.readImage(file, (data.get("WIDTH"), data.get("HEIGHT")), { "ROTATION":data.get("ROTATION", 0), "MIRROR": data.get("MIRROR", False)})

            self.createCoverWithMetadata(
                image_width, image_height, data, image_placeholder, filename
            )
            if self.connected_progress_bar:
                value = self.progress_bar.value() + progress
                # print("VALUE ", value)
                self.updateProgressBar(value)

    # Run the generator based on given files and generator corresponding camera settings summary
    def exec(self, files: list, show_images: bool = True, combine_original_images: bool = False) -> None:
        self.show_images = show_images
        self.updateProgressBar(0)
        exif = self.readRawMetadata(files)
        self.updateProgressBar(5)
        # print(exif)
        if len(exif) != 0:
            self.generateCover(exif, combine_original_images)
        self.updateProgressBar(100)
        self.disconnectProgressCallback()

    def execSettings(self, exif: dict, show_images: bool = True, combine_original_images: bool = False) -> None:
        self.show_images = show_images
        self.updateProgressBar(0)
        if len(exif) != 0:
            self.generateCover(exif, combine_original_images)
        self.updateProgressBar(100)
        self.disconnectProgressCallback()

    def updateProgressBar(self, value: int) -> None:
        value = min(value, 100)
        if self.connected_progress_callback:
            self.progress_callback.emit(value)
        elif self.connected_progress_bar:
            self.progress_bar.setValue(value)
            QApplication.processEvents()

    # Called by Worker Thread to send update signal to Main Thread
    # Must be called before execution
    def connectProgressCallback(self, callback):
        self.progress_callback = callback
        self.connected_progress_callback = True

    def disconnectProgressCallback(self):
        if self.connected_progress_callback:
            self.progress_callback = None
            self.connected_progress_callback = False

    def connectToProgressBar(self, progress_bar: QProgressBar) -> None:
        self.progress_bar = progress_bar
        self.connected_progress_bar = True

    def disconnectProgressBar(self) -> None:
        self.progress_bar = None
        self.connected_progress_bar = False


if __name__ == "__main__":
    # "J:/2024_03/20240319/JPG/IMG20240319154927.jpg", "J:/2024_03/20240328/RAW/DSCF0067.RAF","J:/2024_03/20240319/RAW/IMG_1515.CR2","J:/2024_03/20240331/DSCF0080.RAF"
    # "J:/2024_03/20240319/RAW/IMG_1515.CR2"
    # files = ["J:/2024_03/20240316/RAW/IMG_0840.CR2"]
    files = ["J:/DSCF0082.RAF","J:/DSCF0083.RAF"]
    settings = AppSettings(os.getcwd()+"/settings.json")
    BRAND_LOGO_PATH = settings.getSettings().get("settings").get("Brand_Logo_Path")
    gen = MetadataGenerator(BRAND_LOGO_PATH, settings)
    # gen.read_raw_metadata(files)
    gen.exec(files, True, True)
    # gen.read_image(files[0], (3648, 2736))
