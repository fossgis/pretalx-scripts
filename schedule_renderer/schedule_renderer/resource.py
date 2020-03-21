import os.path

class Resource:
    def __init__(self, code, url_prefix, **kwargs):
        if kwargs["resource"].startswith("https://") or kwargs["resource"].startswith("http://"):
            self.url = kwargs["resource"]
        else:
            self.url = "{}{}".format(url_prefix, kwargs["resource"])
        self.description = kwargs["description"]
        self.code = code
        self.href = None

    def from_list(resources, code, url_prefix):
        result = []
        for item in resources:
            result.append(Resource(code, url_prefix, **item))
        return result

    def get_filename(self):
        filename = self.url.split("/")[-1]
        if not filename:
            raise Exception("empty filename part of attachment URL {}".format(self.url))
        return filename

    def get_cleaned_filename(self):
        filename_escaped = ""
        filename = self.get_filename()
        for c in filename:
            if c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKMNLOPQRSTUVWXYZ_-.0123456789":
                filename_escaped += c
            else:
                filename_escaped += "_"
        return "{}_{}".format(self.code, filename_escaped)

    def set_href(self, directory):
        """Set href attribute to be used for links in templates"""
        self.href = "{}/{}".format(directory, self.get_cleaned_filename())

    def get_destination_path(self, destination_directory):
        filename = self.get_cleaned_filename()
        return os.path.join(destination_directory, self.get_cleaned_filename())
