import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { CalendarDays, Globe, Tag, Clock, AlarmClock, CalendarPlus, Award, MapPin } from "lucide-react";
import { Conference } from "@/types/conference";
import { formatDistanceToNow, parseISO, isValid, format, parse, addDays } from "date-fns";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useState, useEffect } from "react";
import { getDeadlineInLocalTime } from '@/utils/dateUtils';
import { getAllDeadlines, getNextUpcomingDeadline, getUpcomingDeadlines, getDaysRemaining, getCountdownColorClass } from '@/utils/deadlineUtils';

interface ConferenceDialogProps {
  conference: Conference;
  allYears: Conference[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const eraRatingLabel = (rating: string) => {
  switch (rating) {
    case 'a': return { label: 'A', color: 'bg-emerald-100 text-emerald-700 border-emerald-200' };
    case 'b': return { label: 'B', color: 'bg-blue-100 text-blue-700 border-blue-200' };
    case 'c': return { label: 'C', color: 'bg-gray-100 text-gray-600 border-gray-200' };
    default: return { label: rating.toUpperCase(), color: 'bg-gray-100 text-gray-600 border-gray-200' };
  }
};

const ConferenceDialog = ({ conference: initialConference, allYears, open, onOpenChange }: ConferenceDialogProps) => {
  const [selectedYear, setSelectedYear] = useState(initialConference.year);

  // Reset selected year when dialog opens with a different conference
  useEffect(() => {
    if (open) {
      setSelectedYear(initialConference.year);
    }
  }, [open, initialConference.year]);

  // Get the conference for the selected year
  const conference = allYears.find(c => c.year === selectedYear) || initialConference;

  const upcomingDeadlines = getUpcomingDeadlines(conference);
  const allDeadlines = getAllDeadlines(conference);
  const nextDeadline = getNextUpcomingDeadline(conference);
  const deadlineDate = nextDeadline ? getDeadlineInLocalTime(nextDeadline.date, nextDeadline.timezone || conference.timezone) : null;

  const [countdown, setCountdown] = useState<string>('');

  const getLocationString = () => {
    if (conference.venue) return conference.venue;
    const parts = [conference.city, conference.country].filter(Boolean);
    return parts.join(", ") || "Location TBD";
  };

  const location = getLocationString();

  useEffect(() => {
    const calculateTimeLeft = () => {
      if (!deadlineDate || !isValid(deadlineDate)) {
        setCountdown('TBD');
        return;
      }

      const now = new Date();
      const difference = deadlineDate.getTime() - now.getTime();

      if (difference <= 0) {
        setCountdown('Deadline passed');
        return;
      }

      const days = Math.floor(difference / (1000 * 60 * 60 * 24));
      const hours = Math.floor((difference % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const minutes = Math.floor((difference % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((difference % (1000 * 60)) / 1000);

      setCountdown(`${days}d ${hours}h ${minutes}m ${seconds}s`);
    };

    calculateTimeLeft();
    const timer = setInterval(calculateTimeLeft, 1000);
    return () => clearInterval(timer);
  }, [deadlineDate]);

  const getCountdownColor = () => {
    if (!deadlineDate || !isValid(deadlineDate)) return "text-neutral-600";
    const daysRemaining = Math.ceil((deadlineDate.getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24));
    if (daysRemaining <= 7) return "text-red-600";
    if (daysRemaining <= 30) return "text-orange-600";
    return "text-green-600";
  };

  const createCalendarEvent = (type: 'google' | 'apple') => {
    try {
      if (!conference.deadline || conference.deadline === 'TBD') {
        throw new Error('No valid deadline found');
      }

      const deadlineDate = parseISO(conference.deadline);
      if (!isValid(deadlineDate)) {
        throw new Error('Invalid deadline date');
      }

      const endDate = new Date(deadlineDate.getTime() + (60 * 60 * 1000));

      const formatDateForCal = (date: Date) => format(date, "yyyyMMdd'T'HHmmss'Z'");

      const title = encodeURIComponent(`${conference.title} deadline`);
      const locationStr = encodeURIComponent(location);
      const description = encodeURIComponent(
        `Paper Submission Deadline for ${conference.full_name || conference.title}\n` +
        `Dates: ${conference.date}\n` +
        `Location: ${location}\n` +
        (conference.link ? `Website: ${conference.link}` : '')
      );

      if (type === 'google') {
        const url = `https://calendar.google.com/calendar/render?action=TEMPLATE` +
          `&text=${title}` +
          `&dates=${formatDateForCal(deadlineDate)}/${formatDateForCal(endDate)}` +
          `&details=${description}` +
          `&location=${locationStr}` +
          `&sprop=website:${encodeURIComponent(conference.link || '')}`;
        window.open(url, '_blank');
      } else {
        const url = `data:text/calendar;charset=utf8,BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
URL:${conference.link || ''}
DTSTART:${formatDateForCal(deadlineDate)}
DTEND:${formatDateForCal(endDate)}
SUMMARY:${title}
DESCRIPTION:${description}
LOCATION:${location}
END:VEVENT
END:VCALENDAR`;

        const link = document.createElement('a');
        link.href = url;
        link.download = `${conference.title.toLowerCase().replace(/\s+/g, '-')}-deadline.ics`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }
    } catch (error) {
      console.error("Error creating calendar event:", error);
      alert("Sorry, there was an error creating the calendar event. Please try again.");
    }
  };

  const formatDeadlineDisplay = () => {
    if (!deadlineDate || !isValid(deadlineDate)) return null;

    const localTZ = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return (
      <div className="text-sm text-neutral-500">
        <div>{format(deadlineDate, "MMMM d, yyyy 'at' HH:mm:ss")} ({localTZ})</div>
        {conference.timezone && conference.timezone !== localTZ && (
          <div className="text-xs">
            Conference timezone: {conference.timezone}
          </div>
        )}
      </div>
    );
  };

  const getLocalDeadline = (dateString: string | undefined) => {
    if (!dateString || dateString === 'TBD') return null;
    return getDeadlineInLocalTime(dateString, conference.timezone);
  };

  const formatDeadlineDate = (dateString: string | undefined) => {
    if (!dateString || dateString === 'TBD') return dateString || 'TBD';

    const localDate = getLocalDeadline(dateString);
    if (!localDate || !isValid(localDate)) return dateString;

    const localTZ = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return `${format(localDate, "MMMM d, yyyy")} (${localTZ})`;
  };

  // Deadlines to show: upcoming if available, otherwise all
  const deadlinesToShow = upcomingDeadlines.length > 0 ? upcomingDeadlines : allDeadlines;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-lg w-full max-h-[85vh] overflow-y-auto"
      >
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold text-blue-600 flex items-center gap-2">
            {conference.title} {conference.year}
            {conference.era_rating && (
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold border ${eraRatingLabel(conference.era_rating).color}`}>
                ERA {eraRatingLabel(conference.era_rating).label}
              </span>
            )}
          </DialogTitle>
          <DialogDescription className="text-base text-gray-700">
            {conference.full_name}
          </DialogDescription>
        </DialogHeader>

        {/* Year selector with location */}
        {allYears.length > 0 && (
          <div className="border rounded-lg overflow-hidden">
            {allYears.map(conf => {
              const loc = [conf.city, conf.country].filter(Boolean).join(", ") || "TBD";
              const isSelected = conf.year === selectedYear;
              return (
                <button
                  key={conf.year}
                  onClick={() => setSelectedYear(conf.year)}
                  className={`w-full flex items-center justify-between px-3 py-2 text-sm transition-colors border-b last:border-b-0 ${
                    isSelected
                      ? 'bg-blue-50 text-blue-800'
                      : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <span className={`font-medium ${isSelected ? 'text-blue-800' : ''}`}>
                    {conf.title} {conf.year}
                  </span>
                  <span className={`text-xs ${isSelected ? 'text-blue-600' : 'text-gray-400'}`}>
                    {loc}
                  </span>
                </button>
              );
            })}
          </div>
        )}

        {/* Rankings */}
        {conference.rankings && (
          <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg p-3">
            <Award className="h-5 w-5 mt-0.5 text-amber-600 flex-shrink-0" />
            <div>
              <p className="font-medium text-amber-800 text-sm">Rankings</p>
              <p className="text-sm text-amber-700">{conference.rankings}</p>
            </div>
          </div>
        )}

        <div className="space-y-4">
          <div className="space-y-3">
            <div className="flex items-start gap-2">
              <CalendarDays className="h-5 w-5 mt-0.5 text-gray-500" />
              <div>
                <p className="font-medium">Dates</p>
                <p className="text-sm text-gray-500">{conference.date}</p>
              </div>
            </div>

            <div className="flex items-start gap-2">
              <MapPin className="h-5 w-5 mt-0.5 text-gray-500" />
              <div>
                <p className="font-medium">Venue</p>
                <p className="text-sm text-gray-500">
                  {conference.venue || [conference.city, conference.country].filter(Boolean).join(", ")}
                </p>
              </div>
            </div>

            <div className="flex items-start gap-2">
              <Clock className="h-5 w-5 mt-0.5 text-gray-500" />
              <div className="space-y-2 flex-1">
                <p className="font-medium">Important Deadlines</p>
                <div className="text-sm text-gray-500 space-y-2">
                  {deadlinesToShow.length > 0 ? (
                    deadlinesToShow.map((deadline, index) => {
                      const isNext = nextDeadline && deadline.date === nextDeadline.date && deadline.type === nextDeadline.type;
                      const daysRemaining = getDaysRemaining(deadline, conference.timezone);
                      const daysColorClass = getCountdownColorClass(daysRemaining);
                      const isPast = daysRemaining !== null && daysRemaining <= 0;
                      return (
                        <div
                          key={`${deadline.type}-${index}`}
                          className={`rounded-md p-2 ${
                            isNext ? 'bg-blue-100 border border-blue-200' :
                            isPast ? 'bg-gray-50 opacity-60' : 'bg-gray-100'
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <p className={`flex-1 ${isNext ? 'font-medium text-blue-800' : ''} ${isPast ? 'line-through' : ''}`}>
                              {deadline.label}: {formatDeadlineDate(deadline.date)}
                              {isNext && <span className="ml-2 text-xs">(Next)</span>}
                            </p>
                            {daysRemaining !== null && daysRemaining > 0 && (
                              <span className={`text-xs font-medium whitespace-nowrap ${daysColorClass}`}>
                                {daysRemaining} {daysRemaining === 1 ? 'day' : 'days'}
                              </span>
                            )}
                            {isPast && (
                              <span className="text-xs text-gray-400 whitespace-nowrap">passed</span>
                            )}
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div className="bg-gray-100 rounded-md p-2">
                      <p>No deadlines available</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {nextDeadline && (
            <div className="flex items-center">
              <AlarmClock className={`h-5 w-5 mr-3 flex-shrink-0 ${getCountdownColor()}`} />
              <div>
                <span className={`font-medium ${getCountdownColor()}`}>
                  {countdown}
                </span>
                {formatDeadlineDisplay()}
              </div>
            </div>
          )}

          {Array.isArray(conference.tags) && conference.tags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {conference.tags.map((tag) => (
                <span key={tag} className="tag">
                  <Tag className="h-3 w-3 mr-1" />
                  {tag}
                </span>
              ))}
            </div>
          )}

          {conference.note && (
            <div
              className="text-sm text-neutral-600 mt-2 p-3 bg-neutral-50 rounded-lg"
              dangerouslySetInnerHTML={{
                __html: conference.note.replace(
                  /<a(.*?)>/g,
                  '<a$1 style="color: #3b82f6; font-weight: 500; text-decoration: underline; text-underline-offset: 2px;">'
                )
              }}
            />
          )}

          <div className="flex items-center justify-between pt-2">
            {conference.link && (
              <Button
                variant="ghost"
                size="sm"
                className="text-base text-primary hover:underline p-0"
                asChild
              >
                <a
                  href={conference.link}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Visit website
                </a>
              </Button>
            )}

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-sm focus-visible:ring-0 focus:outline-none"
                >
                  <CalendarPlus className="h-4 w-4 mr-2" />
                  Add to Calendar
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="bg-white" align="end">
                <DropdownMenuItem
                  className="text-neutral-800 hover:bg-neutral-100"
                  onClick={() => createCalendarEvent('google')}
                >
                  Add to Google Calendar
                </DropdownMenuItem>
                <DropdownMenuItem
                  className="text-neutral-800 hover:bg-neutral-100"
                  onClick={() => createCalendarEvent('apple')}
                >
                  Add to Apple Calendar
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ConferenceDialog;
