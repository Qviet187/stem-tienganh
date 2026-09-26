class SoundManager:
    @staticmethod
    def get_sound_tag(sound_name):
        sound_files = {
            "correct": "/assets/correct.mp3",
            "wrong_off": "/assets/incorrect_off.mp3",
            "wrong_on": "/assets/metal_pipe.mp3"
        }
        audio_path = sound_files.get(sound_name, "")
        if not audio_path:
            return ""
        return f"""
            <audio id="globalSound" src="{audio_path}" autoplay></audio>
            <script>
                let snd = document.getElementById('globalSound');
                snd.volume = 0.8;
                snd.play().catch(e => console.log("Trình duyệt chặn autoplay:", e));
            </script>
        """
