import pygame



successVoicePath = 'PAKS-SOUNDTRACK/Success.wav'
errorVoicePath = 'PAKS-SOUNDTRACK/Error.wav'
nextDayVoicePath = 'PAKS-SOUNDTRACK/NextDay.wav'
nextHourVoicePath = 'PAKS-SOUNDTRACK/NextHour.wav'
undefinedVoicePath = 'PAKS-SOUNDTRACK/Undefined.wav'
alarmVoicePath = 'PAKS-SOUNDTRACK/blacklist_alarm.wav'
tcVoicePath = 'PAKS-SOUNDTRACK/nowTC.wav'
tcErrorVoicePath = 'PAKS-SOUNDTRACK/errorTC.wav'
tcUndefinedVoicePath = 'PAKS-SOUNDTRACK/undefinedTC.wav'
nowFingerVoicePath = 'PAKS-SOUNDTRACK/nowFinger.wav'


pygame.mixer.init(frequency=48750)
soundSuccess = pygame.mixer.Sound(successVoicePath)
soundError = pygame.mixer.Sound(errorVoicePath)
soundNextday = pygame.mixer.Sound(nextDayVoicePath)
soundUndefined = pygame.mixer.Sound(undefinedVoicePath)
soundAlarm = pygame.mixer.Sound(alarmVoicePath)
soundTC = pygame.mixer.Sound(tcVoicePath)
soundTCError = pygame.mixer.Sound(tcErrorVoicePath)
soundTCUndefined = pygame.mixer.Sound(tcUndefinedVoicePath)
soundNowFinger = pygame.mixer.Sound(nowFingerVoicePath)
soundNextHour = pygame.mixer.Sound(nextHourVoicePath)


def play_sound(sound):
    playing = sound.play()




