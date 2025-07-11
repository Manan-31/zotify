from errno import ENOENT
from pathlib import Path
from subprocess import PIPE, Popen

from music_tag import load_file
from mutagen.oggvorbis import OggVorbisHeaderError

from zotify.utils import AudioFormat, MetadataEntry, Quality


class TranscodingError(RuntimeError): ...


class LocalFile:
    def __init__(
        self,
        path: Path,
        audio_format: AudioFormat | None = None,
        bitrate: int = -1,
    ):
        self.__path = path
        self.__audio_format = audio_format
        self.__bitrate = bitrate

    def transcode(
        self,
        audio_format: AudioFormat | None = None,
        download_quality: Quality | None = None,
        bitrate: int = -1,
        replace: bool = False,
        ffmpeg: str = "",
        opt_args: list[str] = [],
    ) -> None:
        """
        Use ffmpeg to transcode a saved audio file
        Args:
            audio_format: Audio format to transcode file to
            bitrate: Bitrate to transcode file to in kbps
            replace: Replace existing file
            ffmpeg: Location of FFmpeg binary
            opt_args: Additional arguments to pass to ffmpeg
        """
        if not audio_format:
            audio_format = self.__audio_format
        if audio_format:
            ext = audio_format.value.ext
        else:
            ext = self.__path.suffix[1:]

        cmd = [
            ffmpeg if ffmpeg != "" else "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(self.__path),
        ]
        path = self.__path.parent.joinpath(
            self.__path.name.rsplit(".", 1)[0] + "." + ext
        )
        if self.__path == path:
            raise TranscodingError(
                f"Cannot overwrite source, target file {path} already exists."
            )

        if bitrate > 0:
            cmd.extend(["-b:a", str(bitrate) + "k"])
        else:
            cmd.extend(["-b:a", str(Quality.get_bitrate(download_quality)) + "k"])
        cmd.extend(["-c:a", audio_format.value.name]) if audio_format else None
        cmd.extend(opt_args)
        cmd.append(str(path))

        try:
            process = Popen(cmd, stdin=PIPE)
            process.wait()
        except OSError as e:
            if e.errno == ENOENT:
                raise TranscodingError("FFmpeg was not found")
            else:
                raise
        if process.returncode != 0:
            raise TranscodingError(
                f'`{" ".join(cmd)}` failed with error code {process.returncode}'
            )

        if replace:
            self.__path.unlink()
        self.__path = path
        self.__audio_format = audio_format
        self.__bitrate = bitrate

    def write_metadata(self, metadata: list[MetadataEntry]) -> None:
        """
        Write metadata to file
        Args:
            metadata: key-value metadata dictionary
        """
        f = load_file(self.__path)
        f.save()
        for m in metadata:
            try:
                f[m.name] = m.value
            except KeyError:
                pass  # TODO
        try:
            f.save()
        except OggVorbisHeaderError:
            pass  # Thrown when using untranscoded file, nothing breaks.

    def write_cover_art(self, image: bytes) -> None:
        """
        Write cover artwork to file
        Args:
            image: raw image data
        """
        f = load_file(self.__path)
        f["artwork"] = image
        try:
            f.save()
        except OggVorbisHeaderError:
            pass  # Thrown when using untranscoded file, nothing breaks.

    def get_metadata(self, tag: str) -> str:
        """
        Gets metadata from file
        Args:
            tag: metadata tag to be retrieved
        """
        f = load_file(self.__path)
        return f[tag].value

    def clean_filename(self) -> None:
        """
        Removes tmp suffix on filename
        Args:
            None
        """
        path = self.__path
        clean = path.name.replace("_tmp", "")
        path.rename(path.parent.joinpath(clean))
