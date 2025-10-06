/**
 * Sound Effects Manager
 * Handles playing AI-generated sound effects for correct/incorrect answers
 */

class SoundManager {
    constructor() {
        this.sounds = {
            correct: null,
            incorrect: null
        };
        this.enabled = true;
        this.volume = 0.7;
        
        this.init();
    }
    
    init() {
        // Preload sound files
        this.loadSound('correct', '/static/sounds/correct.wav');
        this.loadSound('incorrect', '/static/sounds/incorrect.wav');
    }
    
    loadSound(name, url) {
        try {
            const audio = new Audio(url);
            audio.preload = 'auto';
            audio.volume = this.volume;
            this.sounds[name] = audio;
            console.log(`Sound loaded: ${name}`);
        } catch (error) {
            console.warn(`Failed to load sound ${name}:`, error);
        }
    }
    
    playSound(type) {
        if (!this.enabled) return;
        
        const sound = this.sounds[type];
        if (!sound) {
            console.warn(`Sound not available: ${type}`);
            return;
        }
        
        try {
            // Reset audio to beginning and play
            sound.currentTime = 0;
            sound.play().catch(error => {
                console.warn(`Failed to play sound ${type}:`, error);
            });
        } catch (error) {
            console.warn(`Error playing sound ${type}:`, error);
        }
    }
    
    playCorrect() {
        this.playSound('correct');
    }
    
    playIncorrect() {
        this.playSound('incorrect');
    }
    
    setEnabled(enabled) {
        this.enabled = enabled;
    }
    
    setVolume(volume) {
        this.volume = Math.max(0, Math.min(1, volume));
        Object.values(this.sounds).forEach(sound => {
            if (sound) sound.volume = this.volume;
        });
    }
}

// Create global sound manager instance
window.soundManager = new SoundManager();

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SoundManager;
}







