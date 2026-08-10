

from rest_framework import serializers

from apps.sites.serializers import SiteImageSerializer


class SiteImageUploadService:
    def __init__(self, site, user):
        self.site = site
        self.user = user

    def upload(self, request):

        uploaded = []
        failed = []

        images = request.FILES.getlist("image")

        for image in images:
            data = {}
            for key, values in request.data.lists():
                if key == "image":
                    data[key] = image
                else:
                    data[key] = values[0] if len(values) == 1 else values

            serializer = SiteImageSerializer(
                data=data,
                context={
                    "request": request,
                    "site": self.site,
                },
            )

            try:
                serializer.is_valid(raise_exception=True)

                instance = serializer.save(
                    site=self.site,
                    created_by=self.user,
                )

                uploaded.append(SiteImageSerializer(instance).data)

            except serializers.ValidationError as exc:
                failed.append(
                    {
                        "file_name": image.name,
                        "errors": exc.detail,
                    }
                )

        return {
            "uploaded": uploaded,
            "failed": failed,
        }
